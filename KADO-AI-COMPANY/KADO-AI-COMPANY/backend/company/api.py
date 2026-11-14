"""Authenticated local control plane; existing KADO is the external CEO."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .engine import Engine
from .registry import AGENTS, AGENT_BY_ID, TOOL_CATALOG
from .store import Store


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    kind: Literal["workspace_audit", "llm_task"] = "workspace_audit"
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    timeout_seconds: float | None = Field(default=None, ge=1, le=3600)


class Action(BaseModel):
    action: Literal["pause", "resume", "cancel", "retry", "approve", "reject"]


class Switch(BaseModel):
    enabled: bool


class MemoryCreate(BaseModel):
    scope: Literal["agent", "company", "project", "conversation", "decision", "error"]
    scope_id: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    source_task_id: str | None = None


class Claim(BaseModel):
    agent_id: str
    claim: str = Field(min_length=1, max_length=10000)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class DebateCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    claims: list[Claim] = Field(min_length=2, max_length=10)
    max_rounds: int = Field(default=2, ge=1, le=3)


class ApprovalCreate(BaseModel):
    action: Literal["publish", "delete", "deploy", "payment", "purchase", "account_permissions", "call_recording"]
    description: str = Field(min_length=1, max_length=2000)
    task_id: str | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]


class KadoHeartbeat(BaseModel):
    instance_id: str = Field(min_length=8, max_length=100)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pid: int = Field(ge=1)
    phase: Literal["adapter_loaded", "host_ready", "tool_call_verified", "stopped"]
    adapter_version: str = Field(default="0.1.1", max_length=40)


def connector_manifest() -> list[dict[str, Any]]:
    definitions = [
        ("kado", "Mevcut KADO", "Mevcut KADO giriş noktası incelendi; entegre başlatıcıdan güncel bağlantı sinyali bekleniyor."),
        ("whatsapp", "WhatsApp köprüsü", "Mevcut taşıma kodu ve gerçek hesap doğrulanmadı."),
        ("whatsapp_calls", "WhatsApp aramaları", "Giden/gelen arama, ses gönderme ve alma ayrı ayrı doğrulanmalı."),
        ("instagram", "Instagram", "Resmî API adaptörü ve OAuth bağlantısı bu teslimatta uygulanmadı."),
        ("tiktok", "TikTok", "Resmî API adaptörü ve OAuth bağlantısı bu teslimatta uygulanmadı."),
        ("youtube", "YouTube", "Resmî API adaptörü ve OAuth bağlantısı bu teslimatta uygulanmadı."),
        ("facebook", "Facebook", "Resmî API adaptörü ve OAuth bağlantısı bu teslimatta uygulanmadı."),
        ("emine", "Emine üretim hattı", "Mevcut Piper/ElevenLabs, görsel, dudak ve FFmpeg girişleri bağlanmadı."),
    ]
    return [{"id": id_, "name": name, "status": "unavailable", "capabilities": [],
             "reason": reason, "verified": False} for id_, name, reason in definitions]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.database_url)
    engine = Engine(store, settings)
    started = time.monotonic()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.init()
        await engine.start()
        try:
            yield
        finally:
            await engine.stop()
            store.close()

    app = FastAPI(title="KADO AI Company", version="0.1.0", lifespan=lifespan)
    app.state.settings, app.state.store, app.state.engine = settings, store, engine
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
    bearer = HTTPBearer(auto_error=False)

    async def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or not secrets.compare_digest(credentials.credentials, settings.api_token):
            raise HTTPException(401, "Geçerli yerel API anahtarı gerekiyor.", headers={"WWW-Authenticate": "Bearer"})

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        try:
            declared_length = int(request.headers.get("content-length", "0") or "0")
        except ValueError:
            return JSONResponse({"detail": "Geçersiz Content-Length."}, status_code=400)
        if declared_length < 0:
            return JSONResponse({"detail": "Geçersiz Content-Length."}, status_code=400)
        if declared_length > 1_000_000:
            return JSONResponse({"detail": "İstek boyutu sınırı 1 MB."}, status_code=413)
        if request.method in {"POST", "PUT", "PATCH"}:
            chunks, received = [], 0
            async for chunk in request.stream():
                received += len(chunk)
                if received > 1_000_000:
                    return JSONResponse({"detail": "İstek boyutu sınırı 1 MB."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    protected = [Depends(authenticate)]

    def kado_connection():
        record = store.get_setting("integration.kado", {})
        age = max(0, time.time() - float(record.get("last_seen_epoch", 0)))
        live = age < 35 and record.get("phase") in {"host_ready", "tool_call_verified"}
        return {**{k: v for k, v in record.items() if k != "last_seen_epoch"},
                "connected": live, "last_seen_age_seconds": round(age, 1) if record else None,
                "scope": "Existing KADO runtime adapter heartbeat; voice/WhatsApp are separate tests."}

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "service": "kado-ai-company", "version": "0.1.0"}

    @app.get("/api/agents", dependencies=protected)
    async def agents():
        return AGENTS

    @app.get("/api/tools", dependencies=protected)
    async def tools():
        return TOOL_CATALOG

    @app.get("/api/tasks", dependencies=protected)
    async def tasks(status: str | None = None, limit: int = 100):
        return store.list_tasks(status=status, limit=max(1, min(limit, 500)))

    @app.post("/api/tasks", dependencies=protected, status_code=201)
    async def create_task(body: TaskCreate):
        task = store.create_task(title=body.title, kind=body.kind, input=body.input,
                                 idempotency_key=body.idempotency_key,
                                 max_retries=settings.max_retries if body.max_retries is None else body.max_retries,
                                 timeout_seconds=settings.task_timeout if body.timeout_seconds is None else body.timeout_seconds)
        return task

    @app.get("/api/tasks/{task_id}", dependencies=protected)
    async def task(task_id: str):
        result = store.get_task(task_id)
        if not result:
            raise HTTPException(404, "Görev bulunamadı.")
        return result

    @app.post("/api/tasks/{task_id}/action", dependencies=protected)
    async def task_action(task_id: str, body: Action):
        if not store.get_task(task_id):
            raise HTTPException(404, "Görev bulunamadı.")
        try:
            return await engine.action(task_id, body.action)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/events", dependencies=protected)
    async def events(after: int = 0, task_id: str | None = None):
        return store.list_events(after=max(after, 0), task_id=task_id)

    @app.get("/api/tool-calls", dependencies=protected)
    async def tool_calls(task_id: str | None = None):
        return store.list_tool_calls(task_id=task_id)

    @app.get("/api/artifacts/{task_id}/{name}", dependencies=protected)
    async def artifact(task_id: str, name: str):
        if name not in {"report.json", "qa.json", "audit.json", "response.json"} or not store.get_task(task_id):
            raise HTTPException(404, "Kanıt dosyası bulunamadı.")
        base = (settings.data_dir / "artifacts").resolve()
        target = (base / task_id / name).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            raise HTTPException(404, "Kanıt dosyası bulunamadı.")
        return FileResponse(target, filename=name)

    @app.get("/api/connectors", dependencies=protected)
    async def connectors():
        manifest = connector_manifest()
        connection = kado_connection()
        if connection.get("last_seen_at"):
            manifest[0].update(status="connected" if connection["connected"] else "offline",
                capabilities=["task_submit", "task_status", "task_control", "agent_directory"] if connection["connected"] else [],
                verified=connection["connected"],
                reason="Mevcut KADO başlatıcısından güncel bağlantı sinyali alınıyor. Ses ve WhatsApp ayrıca doğrulanmalıdır." if connection["connected"] else "KADO bağlantı sinyali güncel değil; entegre başlatıcıyı kontrol edin.")
        return manifest

    @app.post("/api/integrations/kado/heartbeat", dependencies=protected)
    async def kado_heartbeat(body: KadoHeartbeat):
        if body.source_sha256 != "9c952052a8b02e87a7176064ba00c7e0ddd40ef8cc1eef8145e3f6dea60118a6":
            raise HTTPException(409, "KADO kaynak sürümü incelenen sürümle eşleşmiyor.")
        previous = store.get_setting("integration.kado", {})
        from datetime import datetime, timezone
        record = {**body.model_dump(), "last_seen_epoch": time.time(),
                  "last_seen_at": datetime.now(timezone.utc).isoformat()}
        store.set_setting("integration.kado", record)
        if previous.get("instance_id") != body.instance_id or previous.get("phase") != body.phase:
            store.add_event(None, "integration.kado.state", {"phase": body.phase, "instance_id": body.instance_id}, agent_id="kado")
        return kado_connection()

    @app.get("/api/integrations", dependencies=protected)
    async def integrations():
        connection = kado_connection()
        return {"ceo": "existing_kado", "sdk": "kado_bridge", "rest": "/api", "websocket": "/api/ws/events",
                "connected_to_existing_kado": connection["connected"], "kado_connection": connection,
                "kado_adapter_version": "0.1.1", "whatsapp_verified": False,
                "voice_verified": False, "calls_verified": False,
                "inspection": "python scripts/inspect_existing_kado.py --help",
                "pipeline": [{"stage": stage, "status": "unavailable"} for stage in
                             ["script", "voice", "image", "lip_sync", "edit", "quality", "approval", "publish"]]}

    @app.get("/api/system", dependencies=protected)
    async def system():
        stats = store.stats()
        counts = {state: stats["by_status"].get(state, 0) for state in
                  ["PENDING", "PLANNING", "IN_PROGRESS", "REVIEW", "APPROVED", "REVISION_REQUIRED", "FAILED", "BLOCKED", "PAUSED", "CANCELLED"]}
        disk = shutil.disk_usage(settings.data_dir)
        return {"engine": engine.status(), "counts": counts,
                "kill_switch": store.get_setting("kill_switch", False),
                "resources": {"cpu_count": __import__("os").cpu_count(), "disk_free_bytes": disk.free,
                              "uptime_seconds": round(time.monotonic() - started),
                              "ram_bytes": None, "gpu": None},
                "providers": {"ollama": {"configured": bool(settings.ollama_model), "verified": False},
                              "gemini": {"configured": bool(settings.gemini_api_key), "verified": False}},
                "cost": {"currency": "USD", "total": None, "reason": "Faturalama API'si bağlı değil; maliyet tahmini gösterilmiyor."}}

    @app.post("/api/system/kill-switch", dependencies=protected)
    async def kill_switch(body: Switch):
        result = engine.set_kill_switch(body.enabled)
        if asyncio.iscoroutine(result):
            await result
        return {"enabled": body.enabled}

    @app.get("/api/memory", dependencies=protected)
    async def memory(scope: str | None = None, scope_id: str | None = None):
        return store.list_memory(scope=scope, scope_id=scope_id)

    @app.post("/api/memory", dependencies=protected, status_code=201)
    async def add_memory(body: MemoryCreate):
        if body.source_task_id and not store.get_task(body.source_task_id):
            raise HTTPException(404, "Kaynak görev bulunamadı.")
        result = store.add_memory(body.scope, body.scope_id, body.content, body.source_task_id)
        store.add_event(None, "memory.updated", {"scope": body.scope, "scope_id": body.scope_id, "verified": False})
        return result

    @app.get("/api/approvals", dependencies=protected)
    async def approvals():
        return store.list_approvals()

    @app.post("/api/approvals", dependencies=protected, status_code=201)
    async def propose_approval(body: ApprovalCreate):
        if body.task_id and not store.get_task(body.task_id):
            raise HTTPException(404, "Görev bulunamadı.")
        return store.add_approval(body.task_id, body.action, {"description": body.description, "execution": "not_implemented"})

    @app.post("/api/approvals/{approval_id}", dependencies=protected)
    async def decide_approval(approval_id: str, body: ApprovalDecision):
        try:
            return store.decide_approval(approval_id, body.decision == "approved")
        except (ValueError, KeyError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/debates", dependencies=protected)
    async def debates():
        return store.list_debates()

    @app.post("/api/debates", dependencies=protected, status_code=201)
    async def debate(body: DebateCreate):
        checked = []
        for claim in body.claims:
            if claim.agent_id not in AGENT_BY_ID:
                raise HTTPException(422, "Bilinmeyen ajan.")
            sources = []
            for evidence in claim.evidence:
                source = store.get_task(str(evidence.get("task_id", "")))
                sources.append({"task_id": evidence.get("task_id"), "verified": bool(source and source["status"] == "APPROVED")})
            checked.append({**claim.model_dump(), "source_checks": sources})
        result = store.add_debate(topic=body.topic, claims=checked, max_rounds=body.max_rounds,
                                 status="HUMAN_REVIEW", decision="Kaynak görev durumu kontrol edildi. İddiaların doğruluğu insan değerlendirmesi gerektiriyor; otomatik uzlaşma üretilmedi.")
        store.add_event(None, "debate.review_required", {"topic": body.topic, "max_rounds": body.max_rounds})
        return result

    @app.websocket("/api/ws/events")
    async def websocket_events(websocket: WebSocket):
        await websocket.accept()
        try:
            first = await asyncio.wait_for(websocket.receive_json(), timeout=5)
            if not secrets.compare_digest(str(first.get("token", "")), settings.api_token):
                await websocket.close(code=4401)
                return
            cursor = max(0, int(first.get("after", 0)))
            while True:
                for event in store.list_events(after=cursor):
                    await websocket.send_json(event)
                    cursor = max(cursor, event["id"])
                await asyncio.sleep(0.25)
        except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, TypeError):
            return

    frontend = settings.project_root / "frontend" / "dist"
    if (frontend / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/")
    async def index():
        if (frontend / "index.html").is_file():
            return FileResponse(frontend / "index.html")
        return {"service": "KADO AI Company", "frontend": "npm --prefix frontend ci && npm --prefix frontend run build", "docs": "/docs"}

    return app


app = create_app()
