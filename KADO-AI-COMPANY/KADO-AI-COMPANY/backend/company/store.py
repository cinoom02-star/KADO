"""Transactional task/event store, portable between SQLite and PostgreSQL.

The queue is durable. One application process owns the worker pool; running
multiple independent application processes against one SQLite file is unsupported.
"""
from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any
from uuid import uuid4

from sqlalchemy import (JSON, Column, Float, Integer, MetaData, String, Table, Text,
                        UniqueConstraint, create_engine, event, func, select, update)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, database_url: str):
        self.database_url = database_url
        options: dict[str, Any] = {"future": True, "pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if database_url in ("sqlite://", "sqlite:///:memory:"):
                options["poolclass"] = StaticPool
        self.engine = create_engine(database_url, **options)
        if database_url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def sqlite_configuration(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=30000")
                connection.execute("PRAGMA journal_mode=WAL")
        self.lock = threading.RLock()
        self.metadata = MetaData()
        self.tasks = Table("tasks", self.metadata,
            Column("id", String(36), primary_key=True), Column("title", String(500), nullable=False),
            Column("kind", String(80), nullable=False), Column("input", JSON, nullable=False),
            Column("status", String(40), nullable=False, index=True), Column("assigned_agent_id", String(100)),
            Column("manager_id", String(100)), Column("result", JSON), Column("error", Text),
            Column("retry_count", Integer, nullable=False), Column("max_retries", Integer, nullable=False),
            Column("timeout_seconds", Float, nullable=False), Column("version", Integer, nullable=False),
            Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False),
            Column("idempotency_key", String(255), unique=True), Column("extra", JSON, nullable=False))
        self.events = Table("events", self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True), Column("task_id", String(36), index=True),
            Column("type", String(100), nullable=False), Column("agent_id", String(100)),
            Column("payload", JSON, nullable=False), Column("created_at", String(40), nullable=False))
        self.tools = Table("tool_calls", self.metadata,
            Column("id", String(36), primary_key=True), Column("task_id", String(36), index=True),
            Column("agent_id", String(100), nullable=False), Column("tool", String(100), nullable=False),
            Column("args", JSON), Column("result", JSON), Column("status", String(40), nullable=False),
            Column("error", Text), Column("created_at", String(40), nullable=False))
        self.memories = Table("memories", self.metadata,
            Column("id", String(36), primary_key=True), Column("scope", String(50), nullable=False),
            Column("scope_id", String(255), nullable=False), Column("content", JSON, nullable=False),
            Column("source_task_id", String(36)), Column("created_at", String(40), nullable=False))
        self.approvals = Table("approvals", self.metadata,
            Column("id", String(36), primary_key=True), Column("task_id", String(36)),
            Column("action", String(100), nullable=False), Column("payload", JSON, nullable=False),
            Column("status", String(40), nullable=False), Column("decision", JSON),
            Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False))
        self.debates = Table("debates", self.metadata,
            Column("id", String(36), primary_key=True), Column("task_id", String(36)),
            Column("payload", JSON, nullable=False), Column("created_at", String(40), nullable=False))
        self.settings = Table("settings", self.metadata,
            Column("key", String(100), primary_key=True), Column("value", JSON),
            Column("updated_at", String(40), nullable=False))
        self.messages = Table("inbox", self.metadata,
            Column("id", String(36), primary_key=True), Column("channel", String(50), nullable=False),
            Column("message_id", String(255), nullable=False), Column("sender", String(255), nullable=False),
            Column("payload", JSON, nullable=False), Column("status", String(40), nullable=False),
            Column("task_id", String(36)), Column("result", JSON), Column("created_at", String(40), nullable=False),
            Column("updated_at", String(40), nullable=False), UniqueConstraint("channel", "message_id"))
        self.outbox = Table("outbox", self.metadata,
            Column("id", String(36), primary_key=True), Column("channel", String(50), nullable=False),
            Column("recipient", String(255), nullable=False), Column("payload", JSON, nullable=False),
            Column("dedupe_key", String(255), unique=True), Column("status", String(40), nullable=False),
            Column("attempts", Integer, nullable=False), Column("result", JSON), Column("error", Text),
            Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False))

    def init(self) -> None:
        self.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    @staticmethod
    def _task(row) -> dict | None:
        if row is None:
            return None
        data = dict(row._mapping if hasattr(row, "_mapping") else row)
        extra = data.pop("extra", {}) or {}
        data.update(extra)
        data["type"] = data["kind"]
        data["assigned_to"] = data["assigned_agent_id"]
        return data

    def create_task(self, title: str, kind: str | None = None, input: dict | None = None,
                    idempotency_key: str | None = None, max_retries: int = 2,
                    timeout_seconds: float = 120, **fields) -> dict:
        kind = kind or fields.pop("type", "workspace_audit")
        now = utcnow()
        data = dict(id=str(uuid4()), title=title, kind=kind, input=input or {}, status="PENDING",
                    assigned_agent_id=None, manager_id=None, result=None, error=None, retry_count=0,
                    max_retries=max_retries, timeout_seconds=timeout_seconds, version=1,
                    created_at=now, updated_at=now, idempotency_key=idempotency_key, extra=fields)
        try:
            with self.lock, self.engine.begin() as conn:
                if idempotency_key:
                    old = conn.execute(select(self.tasks).where(self.tasks.c.idempotency_key == idempotency_key)).first()
                    if old:
                        return self._task(old)
                conn.execute(self.tasks.insert().values(**data))
        except IntegrityError:
            if idempotency_key:
                with self.engine.connect() as conn:
                    old = conn.execute(select(self.tasks).where(self.tasks.c.idempotency_key == idempotency_key)).first()
                    if old:
                        return self._task(old)
            raise
        self.add_event(data["id"], "task.created", {"kind": kind, "title": title})
        return self._task(data)

    def get_task(self, task_id: str) -> dict | None:
        with self.engine.connect() as conn:
            return self._task(conn.execute(select(self.tasks).where(self.tasks.c.id == task_id)).first())

    def list_tasks(self, limit: int = 200, status: str | None = None) -> list[dict]:
        query = select(self.tasks).order_by(self.tasks.c.created_at.desc()).limit(min(max(limit, 1), 1000))
        if status:
            query = query.where(self.tasks.c.status == status)
        with self.engine.connect() as conn:
            return [self._task(row) for row in conn.execute(query)]

    def update_task(self, task_id: str, **fields) -> dict:
        fields.pop("id", None)
        if "type" in fields:
            fields["kind"] = fields.pop("type")
        if "assigned_to" in fields:
            fields["assigned_agent_id"] = fields.pop("assigned_to")
        with self.lock, self.engine.begin() as conn:
            old = conn.execute(select(self.tasks).where(self.tasks.c.id == task_id).with_for_update()).first()
            if old is None:
                raise KeyError(task_id)
            columns = set(self.tasks.c.keys()) - {"id", "extra"}
            normal = {key: value for key, value in fields.items() if key in columns}
            extra = dict(old._mapping["extra"] or {})
            extra.update({key: value for key, value in fields.items() if key not in columns})
            normal.update(extra=extra, updated_at=utcnow(), version=old._mapping["version"] + 1)
            conn.execute(update(self.tasks).where(self.tasks.c.id == task_id).values(**normal))
            result = conn.execute(select(self.tasks).where(self.tasks.c.id == task_id)).first()
            return self._task(result)

    def claim_task(self) -> dict | None:
        with self.lock, self.engine.begin() as conn:
            query = select(self.tasks).where(self.tasks.c.status == "PENDING").order_by(self.tasks.c.created_at).limit(1)
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            old = conn.execute(query).first()
            if old is None:
                return None
            result = conn.execute(update(self.tasks).where(self.tasks.c.id == old._mapping["id"], self.tasks.c.status == "PENDING").values(status="PLANNING", updated_at=utcnow(), version=self.tasks.c.version + 1))
            if not result.rowcount:
                return None
            return self._task(conn.execute(select(self.tasks).where(self.tasks.c.id == old._mapping["id"])).first())

    def recover_tasks(self) -> int:
        active = ("PLANNING", "IN_PROGRESS", "REVIEW", "REVISION_REQUIRED")
        with self.lock, self.engine.begin() as conn:
            candidates = list(conn.execute(select(self.tasks).where(self.tasks.c.status.in_(active))))
            # Human review is a durable waiting state. Replaying it could repeat a
            # paid model request and discard an owner's pending review evidence.
            rows = [row for row in candidates if not (
                row.status in {"REVIEW", "REVISION_REQUIRED"} and isinstance(row.result, dict)
                and row.result.get("human_review_required") is True
            )]
            if rows:
                conn.execute(update(self.tasks).where(self.tasks.c.id.in_([row.id for row in rows])).values(status="PENDING", updated_at=utcnow(), version=self.tasks.c.version + 1))
        for row in rows:
            self.add_event(row.id, "task.recovered", {"reason": "Worker restarted; safe workflow will be replayed."})
        return len(rows)

    def add_event(self, task_id: str | None, type: str, payload: dict | None = None, agent_id: str | None = None) -> dict:
        data = dict(task_id=task_id, type=type, payload=payload or {}, agent_id=agent_id, created_at=utcnow())
        with self.lock, self.engine.begin() as conn:
            result = conn.execute(self.events.insert().values(**data))
            data["id"] = result.inserted_primary_key[0]
        return data

    def list_events(self, after: int = 0, task_id: str | None = None, limit: int = 500) -> list[dict]:
        query = select(self.events).where(self.events.c.id > after).order_by(self.events.c.id).limit(min(max(limit, 1), 2000))
        if task_id:
            query = query.where(self.events.c.task_id == task_id)
        with self.engine.connect() as conn:
            return [dict(row._mapping) for row in conn.execute(query)]

    def record_tool(self, task_id: str, agent_id: str, tool: str, args: dict | None = None,
                    status: str = "SUCCEEDED", result: Any = None, error: str | None = None) -> dict:
        data = dict(id=str(uuid4()), task_id=task_id, agent_id=agent_id, tool=tool, args=args or {}, result=result, status=status, error=error, created_at=utcnow())
        with self.lock, self.engine.begin() as conn:
            conn.execute(self.tools.insert().values(**data))
        data["name"] = tool
        return data

    def add_tool_call(self, task_id: str, agent_id: str, name: str, args: dict, result: Any, status: str, error: str | None = None) -> dict:
        return self.record_tool(task_id, agent_id, name, args, status, result, error)

    def list_tool_calls(self, task_id: str | None = None, limit: int = 500) -> list[dict]:
        query = select(self.tools).order_by(self.tools.c.created_at.desc()).limit(min(max(limit, 1), 2000))
        if task_id:
            query = query.where(self.tools.c.task_id == task_id)
        with self.engine.connect() as conn:
            return [dict(row._mapping, name=row._mapping["tool"]) for row in conn.execute(query)]

    def add_memory(self, scope: str, scope_id: str, content: Any, source_task_id: str | None = None) -> dict:
        if scope not in {"agent", "company", "project", "task", "conversation", "source", "decision", "error"}:
            raise ValueError("Unsupported memory scope")
        data = dict(id=str(uuid4()), scope=scope, scope_id=scope_id, content=content, source_task_id=source_task_id, created_at=utcnow())
        with self.lock, self.engine.begin() as conn:
            conn.execute(self.memories.insert().values(**data))
        return data

    def list_memory(self, scope: str | None = None, scope_id: str | None = None, limit: int = 200) -> list[dict]:
        query = select(self.memories).order_by(self.memories.c.created_at.desc()).limit(min(max(limit, 1), 1000))
        if scope:
            query = query.where(self.memories.c.scope == scope)
        if scope_id:
            query = query.where(self.memories.c.scope_id == scope_id)
        with self.engine.connect() as conn:
            return [dict(row._mapping) for row in conn.execute(query)]

    def add_approval(self, task_id: str | None, action: str, payload: dict | None = None) -> dict:
        now = utcnow()
        data = dict(id=str(uuid4()), task_id=task_id, action=action, payload=payload or {}, status="PENDING", decision=None, created_at=now, updated_at=now)
        with self.lock, self.engine.begin() as conn:
            conn.execute(self.approvals.insert().values(**data))
        return data

    def list_approvals(self, status: str | None = None, limit: int = 200) -> list[dict]:
        query = select(self.approvals).order_by(self.approvals.c.created_at.desc()).limit(limit)
        if status:
            query = query.where(self.approvals.c.status == status)
        with self.engine.connect() as conn:
            return [dict(row._mapping) for row in conn.execute(query)]

    def decide_approval(self, approval_id: str, approved: bool, note: str = "", actor: str = "owner") -> dict:
        with self.lock, self.engine.begin() as conn:
            current = conn.execute(select(self.approvals).where(self.approvals.c.id == approval_id).with_for_update()).first()
            if current is None:
                raise KeyError(approval_id)
            if current.status != "PENDING":
                raise ValueError("Approval already decided")
            conn.execute(update(self.approvals).where(self.approvals.c.id == approval_id, self.approvals.c.status == "PENDING").values(status="APPROVED" if approved else "REJECTED", decision={"actor": actor, "note": note}, updated_at=utcnow()))
            return dict(conn.execute(select(self.approvals).where(self.approvals.c.id == approval_id)).first()._mapping)

    def add_debate(self, task_id: str | None = None, payload: dict | None = None, **fields) -> dict:
        data = dict(id=str(uuid4()), task_id=task_id, payload=payload or fields, created_at=utcnow())
        with self.lock, self.engine.begin() as conn:
            conn.execute(self.debates.insert().values(**data))
        return data

    def list_debates(self, task_id: str | None = None, limit: int = 200) -> list[dict]:
        query = select(self.debates).order_by(self.debates.c.created_at.desc()).limit(limit)
        if task_id:
            query = query.where(self.debates.c.task_id == task_id)
        with self.engine.connect() as conn:
            return [dict(row._mapping) for row in conn.execute(query)]

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.engine.connect() as conn:
            row = conn.execute(select(self.settings.c.value).where(self.settings.c.key == key)).first()
            return default if row is None else row.value

    def set_setting(self, key: str, value: Any) -> None:
        with self.lock, self.engine.begin() as conn:
            old = conn.execute(select(self.settings.c.key).where(self.settings.c.key == key)).first()
            if old:
                conn.execute(update(self.settings).where(self.settings.c.key == key).values(value=value, updated_at=utcnow()))
            else:
                conn.execute(self.settings.insert().values(key=key, value=value, updated_at=utcnow()))

    def reserve_message(self, channel: str, message_id: str, sender: str, payload: dict) -> tuple[dict, bool]:
        now = utcnow()
        data = dict(id=str(uuid4()), channel=channel, message_id=message_id, sender=sender, payload=payload, status="RECEIVED", task_id=None, result=None, created_at=now, updated_at=now)
        with self.lock:
            try:
                with self.engine.begin() as conn:
                    conn.execute(self.messages.insert().values(**data))
                return data, True
            except IntegrityError:
                return self.get_message(channel, message_id), False

    def get_message(self, channel: str, message_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(self.messages).where(self.messages.c.channel == channel, self.messages.c.message_id == message_id)).first()
            return dict(row._mapping) if row else None

    def update_message(self, channel: str, message_id: str, **fields) -> dict:
        allowed = {k: v for k, v in fields.items() if k in {"status", "task_id", "result"}}
        with self.lock, self.engine.begin() as conn:
            conn.execute(update(self.messages).where(self.messages.c.channel == channel, self.messages.c.message_id == message_id).values(**allowed, updated_at=utcnow()))
        return self.get_message(channel, message_id)

    def enqueue_outbox(self, channel: str, recipient: str, payload: dict, dedupe_key: str | None = None) -> dict:
        now = utcnow()
        data = dict(id=str(uuid4()), channel=channel, recipient=recipient, payload=payload, dedupe_key=dedupe_key, status="PENDING", attempts=0, result=None, error=None, created_at=now, updated_at=now)
        with self.lock:
            try:
                with self.engine.begin() as conn:
                    conn.execute(self.outbox.insert().values(**data))
            except IntegrityError:
                if not dedupe_key:
                    raise
                with self.engine.connect() as conn:
                    return dict(conn.execute(select(self.outbox).where(self.outbox.c.dedupe_key == dedupe_key)).first()._mapping)
        return data

    def list_outbox(self, status: str | None = None, limit: int = 200) -> list[dict]:
        query = select(self.outbox).order_by(self.outbox.c.created_at).limit(limit)
        if status:
            query = query.where(self.outbox.c.status == status)
        with self.engine.connect() as conn:
            return [dict(row._mapping) for row in conn.execute(query)]

    def update_outbox(self, message_id: str, **fields) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in {"status", "attempts", "result", "error"}}
        with self.lock, self.engine.begin() as conn:
            conn.execute(update(self.outbox).where(self.outbox.c.id == message_id).values(**allowed, updated_at=utcnow()))
            row = conn.execute(select(self.outbox).where(self.outbox.c.id == message_id)).first()
            return dict(row._mapping) if row else None

    def stats(self) -> dict:
        with self.engine.connect() as conn:
            counts = {status: count for status, count in conn.execute(select(self.tasks.c.status, func.count()).group_by(self.tasks.c.status))}
            return {"tasks": sum(counts.values()), "by_status": counts,
                    "tool_calls": conn.execute(select(func.count()).select_from(self.tools)).scalar_one(),
                    "events": conn.execute(select(func.count()).select_from(self.events)).scalar_one(),
                    "memory_entries": conn.execute(select(func.count()).select_from(self.memories)).scalar_one(),
                    "pending_approvals": conn.execute(select(func.count()).select_from(self.approvals).where(self.approvals.c.status == "PENDING")).scalar_one(),
                    "kill_switch": self.get_setting("kill_switch", False)}
