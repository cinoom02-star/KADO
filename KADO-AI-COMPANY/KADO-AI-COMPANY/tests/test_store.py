from concurrent.futures import ThreadPoolExecutor

import pytest

from company.config import Settings, _protected_windows_path
from company.store import Store


def test_queue_claim_is_unique_and_history_survives_restart(tmp_path):
    url = "sqlite:///" + str(tmp_path / "durable.sqlite3")
    store = Store(url)
    store.init()
    tasks = [store.create_task(f"real job {index}", "workspace_audit", {}) for index in range(20)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        claimed = list(executor.map(lambda _: store.claim_task(), range(30)))
    ids = [task["id"] for task in claimed if task]
    assert len(ids) == len(set(ids)) == 20
    store.update_task(tasks[0]["id"], status="APPROVED", result={"artifact": "report.json"})
    store.update_task(tasks[1]["id"], status="PAUSED", paused_from="PLANNING")
    store.update_task(tasks[2]["id"], status="REVIEW", result={"human_review_required": True, "text": "paid generation"})
    store.update_task(tasks[3]["id"], status="REVISION_REQUIRED", result={"human_review_required": True, "text": "owner rejected generation"})
    store.add_event(tasks[0]["id"], "audit.completed", {"verified": True}, "quality-auditor")
    store.close()

    restarted = Store(url)
    restarted.init()
    assert restarted.recover_tasks() == 16
    assert restarted.get_task(tasks[0]["id"])["result"]["artifact"] == "report.json"
    assert restarted.get_task(tasks[1]["id"])["status"] == "PAUSED"
    assert restarted.get_task(tasks[2]["id"])["status"] == "REVIEW"
    assert restarted.get_task(tasks[3]["id"])["status"] == "REVISION_REQUIRED"
    assert len(restarted.list_tasks(status="PENDING")) == 16
    assert any(event["type"] == "audit.completed" for event in restarted.list_events(task_id=tasks[0]["id"]))
    restarted.close()


def test_message_and_task_idempotency_are_durable(tmp_path):
    url = "sqlite:///" + str(tmp_path / "idempotency.sqlite3")
    store = Store(url)
    store.init()
    task = store.create_task("WhatsApp request", "workspace_audit", {}, idempotency_key="whatsapp:actual-id")
    assert store.create_task("duplicate", "workspace_audit", {}, idempotency_key="whatsapp:actual-id")["id"] == task["id"]
    message, fresh = store.reserve_message("whatsapp", "actual-id", "owner", {"text": "audit"})
    assert fresh
    store.update_message("whatsapp", "actual-id", task_id=task["id"], status="DISPATCHED")
    outbox = store.enqueue_outbox("whatsapp", "owner", {"text": "result"}, dedupe_key="task:" + task["id"])
    store.close()

    restarted = Store(url)
    restarted.init()
    duplicate, fresh = restarted.reserve_message("whatsapp", "actual-id", "owner", {"text": "audit"})
    assert not fresh
    assert duplicate["id"] == message["id"]
    assert duplicate["task_id"] == task["id"]
    assert restarted.enqueue_outbox("whatsapp", "owner", {"text": "result"}, dedupe_key="task:" + task["id"])["id"] == outbox["id"]
    restarted.close()


def test_approval_decision_cannot_be_replayed_and_memory_scopes_are_separate(tmp_path):
    store = Store("sqlite:///" + str(tmp_path / "approval.sqlite3"))
    store.init()
    approval = store.add_approval(None, "publish", {"artifact": "result.mp4"})
    assert store.decide_approval(approval["id"], True, "reviewed")["status"] == "APPROVED"
    with pytest.raises(ValueError, match="already decided"):
        store.decide_approval(approval["id"], False)
    store.add_memory("agent", "qa", {"fact": "verified evidence"})
    store.add_memory("agent", "developer", {"fact": "separate scope"})
    assert [item["content"]["fact"] for item in store.list_memory("agent", "qa")] == ["verified evidence"]
    with pytest.raises(ValueError):
        store.add_memory("unrestricted", "x", {})
    store.close()


def test_configuration_preserves_token_and_protects_existing_kado(tmp_path):
    settings = Settings(project_root=tmp_path)
    token = settings.api_token
    assert len(token) >= 24
    assert settings.workspace_root == tmp_path / "data" / "workspace"
    assert Settings(project_root=tmp_path).api_token == token
    assert _protected_windows_path(r"C:\KADO\kado\sessions")
    assert _protected_windows_path(r"c:\kado\KADO-AJANLAR")
    assert not _protected_windows_path(r"C:\KADO\KADO-AI-COMPANY")
    with pytest.raises(ValueError, match="24"):
        Settings(project_root=tmp_path, api_token="insecure")
