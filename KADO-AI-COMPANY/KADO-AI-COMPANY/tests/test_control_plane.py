"""Real HTTP/storage checks for owner review and evidence provenance controls."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient
import pytest

from company.api import create_app
from company.config import Settings


TOKEN = "isolated-control-plane-owner-token"


@pytest.fixture
def client(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "source.txt").write_text("actual source evidence", encoding="utf-8")
    settings = Settings(project_root=tmp_path, workspace_root=workspace, api_token=TOKEN)
    with TestClient(create_app(settings)) as current:
        current.headers.update({"Authorization": f"Bearer {TOKEN}"})
        yield current


def test_memory_create_query_and_source_validation(client):
    created = client.post("/api/memory", json={"scope": "agent", "scope_id": "qa_engineer", "content": "Owner observation"})
    assert created.status_code == 201, created.text
    assert created.json()["scope"] == "agent"
    assert created.json()["scope_id"] == "qa_engineer"
    assert created.json()["content"] == "Owner observation"
    assert client.post("/api/memory", json={"scope": "agent", "scope_id": "senior_fullstack", "content": "Separate observation"}).status_code == 201
    queried = client.get("/api/memory", params={"scope": "agent", "scope_id": "qa_engineer"})
    assert queried.status_code == 200
    assert [entry["id"] for entry in queried.json()] == [created.json()["id"]]
    assert client.post("/api/memory", json={"scope": "agent", "scope_id": "qa_engineer", "content": "Invalid provenance", "source_task_id": "missing-task"}).status_code == 404
    assert client.post("/api/memory", json={"scope": "system", "scope_id": "root", "content": "Denied"}).status_code == 422
    # User supplied memory is auditable and does not claim evidence verification.
    events = client.get("/api/events").json()
    assert any(event["type"] == "memory.updated" and event["payload"]["verified"] is False for event in events)


@pytest.mark.parametrize("decision,expected", [("approved", "APPROVED"), ("rejected", "REJECTED")])
def test_owner_approval_decision_is_one_shot_and_does_not_execute(client, decision, expected):
    created = client.post("/api/approvals", json={"action": "publish", "description": "Review this exact artifact before publication"})
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["status"] == "PENDING"
    assert item["action"] == "publish"
    assert item["payload"]["execution"] == "not_implemented"
    result = client.post(f"/api/approvals/{item['id']}", json={"decision": decision})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == expected
    replay = client.post(f"/api/approvals/{item['id']}", json={"decision": "rejected" if decision == "approved" else "approved"})
    assert replay.status_code == 409
    listed = client.get("/api/approvals").json()
    assert next(approval for approval in listed if approval["id"] == item["id"])["status"] == expected
    assert client.get("/api/tasks").json() == []
    assert client.get("/api/tool-calls").json() == []
    assert client.post("/api/approvals", json={"action": "payment", "description": "Missing task", "task_id": "missing-task"}).status_code == 404


def test_debate_checks_real_source_task_state_and_requires_human_review(client):
    task = client.post("/api/tasks", json={"title": "Verify source", "kind": "workspace_audit", "input": {"path": "."}}).json()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = client.get(f"/api/tasks/{task['id']}").json()["status"]
        if state in {"APPROVED", "FAILED", "BLOCKED"}:
            break
        time.sleep(0.02)
    assert state == "APPROVED"
    body = {"topic": "Compare claims using source evidence", "max_rounds": 2, "claims": [
        {"agent_id": "deep_researcher", "claim": "This source task completed successfully", "evidence": [{"task_id": task["id"]}]},
        {"agent_id": "quality_auditor", "claim": "This other source is missing", "evidence": [{"task_id": "missing-source"}]},
    ]}
    created = client.post("/api/debates", json=body)
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["payload"]["status"] == "HUMAN_REVIEW"
    claims = item["payload"]["claims"]
    assert claims[0]["source_checks"] == [{"task_id": task["id"], "verified": True}]
    assert claims[1]["source_checks"] == [{"task_id": "missing-source", "verified": False}]
    assert any(entry["id"] == item["id"] for entry in client.get("/api/debates").json())
    body["claims"][0]["agent_id"] = "invented-agent"
    assert client.post("/api/debates", json=body).status_code == 422
    body["claims"][0]["agent_id"] = "deep_researcher"
    body["max_rounds"] = 4
    assert client.post("/api/debates", json=body).status_code == 422
