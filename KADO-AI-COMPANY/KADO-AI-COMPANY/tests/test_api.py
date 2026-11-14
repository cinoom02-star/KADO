"""HTTP integration checks against the real queue, tools, database and events.

No successful execution is mocked. The workspace and database belong to tmp_path;
no user KADO folder, account, provider or existing WhatsApp session is touched.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from company.api import create_app
from company.config import Settings


TOKEN = "test-owner-token-only-for-isolated-tests"
TERMINAL = {"APPROVED", "FAILED", "BLOCKED", "CANCELLED"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "hello.txt").write_text("KADO gerçek dosya kanıtı\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "answer.py").write_text("ANSWER = 42\n", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    return Settings(
        project_root=tmp_path,
        data_dir=data,
        workspace_root=workspace,
        database_url=f"sqlite:///{tmp_path / 'company.sqlite3'}",
        api_token=TOKEN,
        worker_concurrency=1,
        max_retries=1,
        task_timeout=15,
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as current:
        current.headers.update({"Authorization": f"Bearer {TOKEN}"})
        yield current


def create_task(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "Gerçek çalışma alanını incele",
        "kind": "workspace_audit",
        "input": {"path": "."},
        **overrides,
    }
    response = client.post("/api/tasks", json=payload)
    assert response.status_code in {200, 201}, response.text
    return response.json()


def wait_task(client: TestClient, task_id: str, expected: set[str] | None = None) -> dict:
    expected = expected or TERMINAL
    deadline = time.monotonic() + 15
    observed = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200, response.text
        observed = response.json()
        if observed["status"] in expected:
            return observed
        time.sleep(0.025)
    pytest.fail(f"Task did not reach {expected}; last observed: {observed}")


def test_health_public_but_commands_require_owner_token(settings: Settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/tasks").status_code == 401
        assert client.post(
            "/api/tasks", json={"title": "Denied", "kind": "workspace_audit", "input": {}}
        ).status_code == 401
        assert client.post("/api/system/kill-switch", json={"enabled": True}).status_code == 401
        assert client.get("/api/tasks", headers={"Authorization": "Bearer incorrect"}).status_code == 401


def test_registry_keeps_existing_kado_and_exactly_four_managers(client: TestClient):
    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 35
    by_id = {agent["id"]: agent for agent in agents}
    assert len(by_id) == 35
    assert {"kado", "cto", "cmo", "crco", "coo"} <= by_id.keys()
    managers = {"cto", "cmo", "crco", "coo"}
    assert all(by_id[manager]["manager_id"] == "kado" for manager in managers)
    specialists = [agent for agent in agents if agent["id"] not in managers | {"kado"}]
    assert len(specialists) == 30
    assert all(agent["manager_id"] in managers for agent in specialists)
    assert all(isinstance(agent["tools"], list) for agent in agents)


def test_real_task_delegation_evidence_and_independent_review(client: TestClient, settings: Settings):
    created = create_task(client)
    task = wait_task(client, created["id"])
    assert task["status"] == "APPROVED", task
    result = task["result"]
    report_path = Path(result["report"]["path"])
    assert report_path.is_file()
    assert report_path.is_relative_to(settings.data_dir)
    report_bytes = report_path.read_bytes()
    assert hashlib.sha256(report_bytes).hexdigest() == result["report"]["sha256"]
    report = json.loads(report_bytes)
    # The actual source digest must survive the generated report, not just a
    # generic success string from the worker.
    source_digest = hashlib.sha256((settings.workspace_root / "hello.txt").read_bytes()).hexdigest()
    assert source_digest in json.dumps(report)
    assert result["qa"]["passed"] is True
    assert result["audit"]["passed"] is True

    calls_response = client.get("/api/tool-calls", params={"task_id": task["id"]})
    assert calls_response.status_code == 200
    calls = calls_response.json()
    assert len(calls) >= 4
    assert all(call["task_id"] == task["id"] for call in calls)
    assert any(call["status"] == "SUCCEEDED" for call in calls)
    events = client.get("/api/events", params={"task_id": task["id"]}).json()
    event_types = {event["type"] for event in events}
    assert {"task.assigned", "tool.completed", "review.completed", "task.completed"} <= event_types
    participants = {event.get("agent_id") for event in events}
    assert {"cto", "senior_fullstack", "qa_engineer", "quality_auditor"} <= participants


def test_idempotent_submission_and_history_survive_restart(settings: Settings):
    with TestClient(create_app(settings)) as first:
        first.headers.update({"Authorization": f"Bearer {TOKEN}"})
        submitted = create_task(first, idempotency_key="owner-request-123")
        duplicate = create_task(first, idempotency_key="owner-request-123")
        assert duplicate["id"] == submitted["id"]
        approved = wait_task(first, submitted["id"])
        assert approved["status"] == "APPROVED", approved
        original_events = first.get("/api/events", params={"task_id": submitted["id"]}).json()
        assert original_events

    with TestClient(create_app(settings)) as restarted:
        restarted.headers.update({"Authorization": f"Bearer {TOKEN}"})
        restored = restarted.get(f"/api/tasks/{submitted['id']}").json()
        assert restored["status"] == "APPROVED"
        assert restored["result"] == approved["result"]
        duplicate = create_task(restarted, idempotency_key="owner-request-123")
        assert duplicate["id"] == submitted["id"]
        tasks = restarted.get("/api/tasks").json()
        assert sum(task["id"] == submitted["id"] for task in tasks) == 1
        restored_events = restarted.get("/api/events", params={"task_id": submitted["id"]}).json()
        assert {event["id"] for event in original_events} <= {event["id"] for event in restored_events}


def test_workspace_boundary_denies_parent_traversal(client: TestClient, settings: Settings):
    outside = settings.workspace_root.parent / "owner-private.txt"
    private_contents = "PRIVATE-TEST-CONTENT-MUST-NOT-BE-IN-RESULTS"
    outside.write_text(private_contents, encoding="utf-8")
    response = client.post(
        "/api/tasks",
        json={"title": "Scope denial", "kind": "workspace_audit", "input": {"path": "../"}},
    )
    if response.status_code in {400, 403, 422}:
        assert private_contents not in response.text
        return
    assert response.status_code in {200, 201}, response.text
    task = wait_task(client, response.json()["id"])
    assert task["status"] in {"BLOCKED", "FAILED"}, task
    assert private_contents not in json.dumps(task)
    assert not (settings.data_dir / "artifacts" / task["id"] / "report.json").exists()


def test_audit_excludes_secrets_sessions_and_external_symlinks(client: TestClient, settings: Settings):
    workspace = settings.workspace_root
    (workspace / ".env").write_text("PRIVATE_API_KEY=not-a-real-secret\n", encoding="utf-8")
    (workspace / "sessions").mkdir()
    (workspace / "sessions" / "credentials.json").write_text("private-session-fixture", encoding="utf-8")
    external = workspace.parent / "private-outside-source.txt"
    external.write_text("outside-source-fixture", encoding="utf-8")
    linked = False
    try:
        (workspace / "external-link.txt").symlink_to(external)
        linked = True
    except (OSError, NotImplementedError):
        # Unprivileged Windows installations may not permit symlink creation.
        pass
    task = wait_task(client, create_task(client)["id"])
    assert task["status"] == "APPROVED", task
    report = json.loads(Path(task["result"]["report"]["path"]).read_text(encoding="utf-8"))
    included = {record["path"] for record in report["files"]}
    assert "hello.txt" in included
    assert ".env" not in included
    assert not any("sessions" in item for item in included)
    assert "external-link.txt" not in included
    excluded = {record["path"] for record in report["excluded"]}
    assert {".env", "sessions"} <= excluded
    if linked:
        assert "external-link.txt" in excluded
    assert hashlib.sha256(external.read_bytes()).hexdigest() not in json.dumps(report)


def test_kill_switch_pause_resume_cancel_are_real_persisted_controls(client: TestClient):
    response = client.post("/api/system/kill-switch", json={"enabled": True})
    assert response.status_code == 200, response.text
    created = create_task(client)
    task_id = created["id"]
    # With the kill switch active no worker may publish a completed artifact.
    time.sleep(0.1)
    assert client.get(f"/api/tasks/{task_id}").json()["status"] != "APPROVED"
    paused = client.post(f"/api/tasks/{task_id}/action", json={"action": "pause"})
    assert paused.status_code == 200, paused.text
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "PAUSED"
    # The global stop also prevents an owner from accidentally resuming work.
    denied_resume = client.post(f"/api/tasks/{task_id}/action", json={"action": "resume"})
    assert denied_resume.status_code == 409, denied_resume.text
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "PAUSED"
    assert client.post("/api/system/kill-switch", json={"enabled": False}).status_code == 200
    resumed = client.post(f"/api/tasks/{task_id}/action", json={"action": "resume"})
    assert resumed.status_code == 200, resumed.text
    assert wait_task(client, task_id)["status"] == "APPROVED"
    assert client.post("/api/system/kill-switch", json={"enabled": True}).status_code == 200
    task_id = create_task(client, title="İptal edilecek ayrı görev")["id"]
    cancelled = client.post(f"/api/tasks/{task_id}/action", json={"action": "cancel"})
    assert cancelled.status_code == 200, cancelled.text
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "CANCELLED"
    assert client.post("/api/system/kill-switch", json={"enabled": False}).status_code == 200
    time.sleep(0.1)
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "CANCELLED"


def test_unconfigured_connectors_never_claim_live_success(client: TestClient):
    response = client.get("/api/connectors")
    assert response.status_code == 200
    connectors = response.json()
    assert connectors
    assert all(connector["status"].lower() not in {"connected", "ready", "active"} for connector in connectors)
    assert all(connector.get("reason") for connector in connectors)


def test_critical_approval_rejection_is_not_accidentally_approved(client: TestClient):
    response = client.post(
        "/api/approvals", json={"action": "publish", "description": "Test yayını için insan kararı"}
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["status"] == "PENDING"
    decision = client.post(f"/api/approvals/{proposal['id']}", json={"decision": "rejected"})
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "REJECTED"
    # A previous owner decision is final; a second conflicting request must fail.
    duplicate = client.post(f"/api/approvals/{proposal['id']}", json={"decision": "approved"})
    assert duplicate.status_code == 409, duplicate.text
    stored = next(row for row in client.get("/api/approvals").json() if row["id"] == proposal["id"])
    assert stored["status"] == "REJECTED"


def test_bounded_debate_preserves_claims_and_requires_human_judgment(client: TestClient):
    topic = "Kanıtsız iddiaları birbirinden ayır"
    response = client.post(
        "/api/debates",
        json={
            "topic": topic,
            "max_rounds": 2,
            "claims": [
                {"agent_id": "deep_researcher", "claim": "Doğrulanmamış birinci iddia", "evidence": []},
                {
                    "agent_id": "social_strategist",
                    "claim": "Doğrulanmamış ikinci iddia",
                    "evidence": [{"task_id": "does-not-exist"}],
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    record = response.json()
    payload = record.get("payload", record)
    assert payload["topic"] == topic
    assert payload["max_rounds"] == 2
    assert payload["status"] == "HUMAN_REVIEW"
    assert len(payload["claims"]) == 2
    assert payload["claims"][1]["source_checks"][0]["verified"] is False
    assert payload["decision"]
    listed = client.get("/api/debates").json()
    assert any(debate["id"] == record["id"] for debate in listed)
    invalid = client.post(
        "/api/debates",
        json={"topic": topic, "max_rounds": 99, "claims": payload["claims"]},
    )
    assert invalid.status_code == 422


def test_websocket_uses_authenticated_event_cursor_replay(client: TestClient):
    created = create_task(client)
    wait_task(client, created["id"])
    events = client.get("/api/events").json()
    assert len(events) >= 2
    after = events[0]["id"]
    with client.websocket_connect("/api/ws/events") as websocket:
        websocket.send_json({"token": TOKEN, "after": after})
        replayed = websocket.receive_json()
        assert replayed["id"] > after
        assert replayed["type"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws/events") as websocket:
            websocket.send_json({"token": "incorrect", "after": 0})
            websocket.receive_json()
