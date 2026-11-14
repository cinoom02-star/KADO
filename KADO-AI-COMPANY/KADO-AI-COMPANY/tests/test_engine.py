"""Real filesystem/queue tests; provider retry is explicitly a mocked HTTP contract test."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from company.config import Settings
from company.engine import Engine
from company.providers import ProviderUnavailable, generate
from company.registry import AGENTS, require_permission
from company.store import Store
from company.tools import WorkspaceTools


def setup_engine(tmp_path):
    settings = Settings(project_root=tmp_path, api_token="t" * 32, max_retries=1)
    (settings.workspace_root / "hello.txt").write_text("Gerçek dosya kanıtı", encoding="utf-8")
    store = Store(settings.database_url)
    store.init()
    return Engine(store, settings), store, settings


async def wait_status(store, task_id, expected, seconds=5):
    async with asyncio.timeout(seconds):
        while True:
            task = store.get_task(task_id)
            if task["status"] in expected:
                return task
            await asyncio.sleep(0.01)


def test_registry_has_35_roles_and_role_tool_permissions():
    assert len(AGENTS) == len({x["id"] for x in AGENTS}) == 35
    assert sum(agent["role"] == "manager" for agent in AGENTS) == 4
    assert sum(agent["role"] == "specialist" for agent in AGENTS) == 30
    require_permission("senior_fullstack", "workspace_inventory")
    with pytest.raises(PermissionError):
        require_permission("instagram_specialist", "workspace_inventory")


def test_tampered_evidence_is_rejected_then_real_retry_is_verified(tmp_path, monkeypatch):
    async def run():
        engine, store, settings = setup_engine(tmp_path)
        real_write = engine.tools.write_json
        corrupted = False

        def write_with_one_corruption(task_id, data, name="report.json"):
            nonlocal corrupted
            result = real_write(task_id, data, name)
            if name == "report.json" and not corrupted:
                corrupted = True
                path = Path(result["path"])
                content = json.loads(path.read_text(encoding="utf-8"))
                content["files"][0]["sha256"] = "0" * 64
                path.write_text(json.dumps(content), encoding="utf-8")
            return result

        monkeypatch.setattr(engine.tools, "write_json", write_with_one_corruption)
        task = store.create_task("Kanıt denetimi", "workspace_audit", {"path": "."}, max_retries=1)
        await engine.start()
        try:
            done = await wait_status(store, task["id"], {"APPROVED", "FAILED", "BLOCKED"})
            assert done["status"] == "APPROVED", done
            assert done["retry_count"] == 1
            assert done["result"]["qa"]["passed"] is True
            assert done["result"]["audit"]["passed"] is True
            events = store.list_events(task_id=task["id"])
            assert any(event["type"] == "revision.requested" for event in events)
            assert any(event["type"] == "review.completed" and event["payload"]["passed"] is False for event in events)
            report = json.loads((settings.data_dir / "artifacts" / task["id"] / "report.json").read_text(encoding="utf-8"))
            assert report["file_count"] == 1
            assert report["files"][0]["sha256"] != "0" * 64
            assert {call["name"] for call in store.list_tool_calls(task_id=task["id"])} == {"workspace_inventory", "write_report", "verify_report", "audit_report"}
        finally:
            await engine.stop()
            store.close()
    asyncio.run(run())


def test_cancel_running_task_does_not_kill_worker(tmp_path, monkeypatch):
    async def run():
        engine, store, _ = setup_engine(tmp_path)
        started = asyncio.Event()
        original = engine.tools.inventory

        async def hold(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(engine.tools, "inventory", hold)
        task = store.create_task("İptal", "workspace_audit", {"path": "."})
        await engine.start()
        try:
            await asyncio.wait_for(started.wait(), 3)
            await engine.action(task["id"], "cancel")
            assert store.get_task(task["id"])["status"] == "CANCELLED"
            await asyncio.sleep(0.05)
            monkeypatch.setattr(engine.tools, "inventory", original)
            next_task = store.create_task("Sonraki gerçek iş", "workspace_audit", {"path": "."})
            done = await wait_status(store, next_task["id"], {"APPROVED", "FAILED", "BLOCKED"})
            assert done["status"] == "APPROVED", done
            assert store.get_task(task["id"])["result"] is None
        finally:
            await engine.stop()
            store.close()
    asyncio.run(run())


def test_timeout_and_kill_switch_enforce_boundaries(tmp_path, monkeypatch):
    async def run():
        engine, store, _ = setup_engine(tmp_path)

        async def hang(*args, **kwargs):
            await asyncio.Event().wait()

        monkeypatch.setattr(engine.tools, "inventory", hang)
        task = store.create_task("Zaman aşımı", "workspace_audit", {}, timeout_seconds=1, max_retries=0)
        await engine.start()
        try:
            done = await wait_status(store, task["id"], {"FAILED"}, seconds=4)
            assert "zaman aşımı" in done["error"]
            await engine.set_kill_switch(True)
            queued = store.create_task("Durdurulmuş kuyruk", "workspace_audit", {})
            await asyncio.sleep(0.2)
            assert store.get_task(queued["id"])["status"] == "PENDING"
            await engine.action(queued["id"], "pause")
            with pytest.raises(ValueError):
                await engine.action(queued["id"], "resume")
        finally:
            await engine.stop()
            store.close()
    asyncio.run(run())


def test_scope_and_secret_exclusions(tmp_path):
    async def run():
        engine, store, settings = setup_engine(tmp_path)
        try:
            (settings.workspace_root / ".env").write_text("PRIVATE=not-for-inventory")
            (settings.workspace_root / "sessions").mkdir()
            (settings.workspace_root / "sessions" / "login.json").write_text("private")
            report = await engine.tools.inventory(".", lambda: asyncio.sleep(0))
            assert [item["path"] for item in report["files"]] == ["hello.txt"]
            assert {item["path"] for item in report["excluded"]} == {".env", "sessions"}
            with pytest.raises(PermissionError):
                engine.tools.target("../")
            with pytest.raises(PermissionError):
                engine.tools.target("sessions")
        finally:
            store.close()
    asyncio.run(run())


def test_provider_429_retry_and_error_redaction_http_contract(monkeypatch):
    """MockTransport tests behavior; it does NOT validate a live Gemini/Ollama service."""
    async def run():
        requests = []

        def handler(request):
            requests.append(request)
            if len(requests) < 3:
                return httpx.Response(429, json={"error": "quota SECRET"})
            return httpx.Response(200, json={"message": {"content": "Sözleşme testi çıktısı"}, "eval_count": 4})

        real_client = httpx.AsyncClient
        monkeypatch.setattr("company.providers.httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
        config = SimpleNamespace(ollama_model="contract-test", ollama_base_url="http://model.test", task_timeout=5)
        result = await generate(config, "brief", "QA", "ollama")
        assert len(requests) == 3
        assert result["text"] == "Sözleşme testi çıktısı"
        assert result["usage"]["output_tokens"] == 4

        def fail(request):
            return httpx.Response(401, text="SECRET_DO_NOT_PERSIST")

        monkeypatch.setattr("company.providers.httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(fail), **kw))
        with pytest.raises(ProviderUnavailable) as error:
            await generate(config, "brief", "QA", "ollama")
        assert "401" in str(error.value)
        assert "SECRET" not in str(error.value)
    asyncio.run(run())
