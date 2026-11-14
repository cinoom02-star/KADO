"""Wrap an explicitly provided existing WhatsApp transport. No sessions are touched.

This is a contract and durable journal, not a WhatsApp implementation. In
particular, Puppeteer messaging does not imply calling support.
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


class UnsupportedCapability(RuntimeError):
    pass


class AmbiguousContact(ValueError):
    pass


class RetryableSendError(RuntimeError):
    """Transport explicitly proves the message was NOT delivered."""


@dataclass(frozen=True)
class Capability:
    supported: bool = False
    verified: bool = False
    evidence: str = ""


class WhatsAppTransport(Protocol):
    def capabilities(self) -> dict[str, Capability]: ...
    def send_text(self, recipient: str, text: str, *, idempotency_key: str) -> str: ...
    def send_voice(self, recipient: str, pcm: bytes, *, sample_rate: int, idempotency_key: str) -> str: ...
    def start_call(self, contact_id: str, *, introduction: str) -> str: ...
    def answer_call(self, call_id: str, *, introduction: str) -> bool: ...
    def hangup(self, call_id: str) -> bool: ...


AI_INTRODUCTION = "Merhaba, ben KADO, yapay zekâ asistanıyım. Sizinle görüşmek için arıyorum."


class WhatsAppJournal:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS inbox (
                    message_id TEXT PRIMARY KEY, sender TEXT NOT NULL, state TEXT NOT NULL,
                    command TEXT, task_id TEXT, result TEXT, error TEXT, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (
                    key TEXT PRIMARY KEY, recipient TEXT NOT NULL, text TEXT NOT NULL,
                    state TEXT NOT NULL, remote_id TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                    error TEXT, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS call_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT, state TEXT,
                    evidence TEXT, updated REAL NOT NULL);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(inbox)")}
            if "command" not in columns:
                db.execute("ALTER TABLE inbox ADD COLUMN command TEXT")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def inbox(self, message_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM inbox WHERE message_id=?", (message_id,)).fetchone()
            return dict(row) if row else None

    def call_event(self, call_id, state, evidence):
        with self.connect() as db:
            db.execute("INSERT INTO call_events(call_id,state,evidence,updated) VALUES (?,?,?,?)",
                       (call_id, state, evidence[:2000], time.time()))


class KadoWhatsAppAdapter:
    def __init__(self, transport: WhatsAppTransport, journal: WhatsAppJournal, *,
                 owner_ids: set[str], command_prefix: str = "KADO,", contacts: dict[str, list[str]] | None = None,
                 allowed_contact_ids: set[str] | None = None):
        if not command_prefix.strip():
            raise ValueError("An explicit nonempty command prefix is required")
        self.transport, self.journal = transport, journal
        self.owner_ids = frozenset(owner_ids)
        self.command_prefix = command_prefix
        self.contacts = contacts or {}
        self.allowed_contact_ids = frozenset(allowed_contact_ids or set())

    def require(self, capability: str):
        cap = self.transport.capabilities().get(capability, Capability())
        if not isinstance(cap, Capability) or not cap.supported or not cap.verified or not cap.evidence:
            raise UnsupportedCapability(f"{capability}: existing transport has no verified capability evidence")
        return cap

    def receive_text(self, message_id: str, sender: str, text: str, dispatch: Callable[..., dict]):
        """Only authenticated owner's prefixed text can dispatch.

        dispatch(command, idempotency_key=...) must use the central engine's durable
        idempotency key. Thus crash after submission cannot create another task.
        Ordinary/non-owner messages are intentionally not sent to a command LLM.
        """
        if not message_id or len(message_id) > 300 or not sender or len(sender) > 300:
            raise ValueError("Stable transport message and sender IDs are required")
        if sender not in self.owner_ids:
            return {"status": "IGNORED", "reason": "sender_not_authorized"}
        if not text.casefold().startswith(self.command_prefix.casefold()):
            return {"status": "IGNORED", "reason": "not_a_command"}
        command = text[len(self.command_prefix):].strip()
        if not command or len(command) > 32000:
            raise ValueError("Command must contain between 1 and 32000 characters")
        with self.journal.lock:
            prior = self.journal.inbox(message_id)
            if prior and prior["sender"] != sender:
                raise PermissionError("Message ID collision between senders")
            if prior and prior["state"] in {"DISPATCHED", "COMPLETED"}:
                return {"status": "DUPLICATE", "task_id": prior["task_id"]}
            if prior and prior.get("command") and prior["command"] != command:
                raise ValueError("Message ID already used for a different command")
            with self.journal.connect() as db:
                db.execute("INSERT OR IGNORE INTO inbox(message_id,sender,state,command,updated) VALUES (?,?,?,?,?)",
                           (message_id, sender, "RECEIVED", command, time.time()))
            try:
                result = dispatch(command, idempotency_key=f"whatsapp:{sender}:{message_id}")
                task_id = result["id"]
                with self.journal.connect() as db:
                    db.execute("UPDATE inbox SET state='DISPATCHED',task_id=?,result=?,error=NULL,updated=? WHERE message_id=?",
                               (task_id, json.dumps(result, ensure_ascii=False), time.time(), message_id))
                return {"status": "DISPATCHED", "task_id": task_id}
            except Exception as exc:
                with self.journal.connect() as db:
                    db.execute("UPDATE inbox SET state='FAILED',error=?,updated=? WHERE message_id=?",
                               (type(exc).__name__, time.time(), message_id))
                raise

    def retry_pending(self, dispatch: Callable[..., dict], *, limit: int = 100):
        """Invoke after backend reconnect; durable owner commands are not lost."""
        with self.journal.connect() as db:
            rows = db.execute("SELECT message_id,sender,command FROM inbox WHERE state IN ('RECEIVED','FAILED') ORDER BY updated LIMIT ?",
                              (max(1, min(limit, 100)),)).fetchall()
        results = []
        for row in rows:
            if not row["command"]:
                continue
            try:
                results.append(self.receive_text(row["message_id"], row["sender"],
                                                 self.command_prefix + row["command"], dispatch))
            except Exception as exc:
                results.append({"message_id": row["message_id"], "status": "FAILED", "error": type(exc).__name__})
        return results

    def collect_completed(self, client, render_result: Callable[[dict], str], *, limit: int = 100):
        """Existing KADO renders the final reply; enqueue it durably for its transport.

        This method does not silently substitute another assistant for KADO.
        The caller controls polling and calls deliver_reply for actual delivery.
        """
        with self.journal.connect() as db:
            rows = db.execute("SELECT message_id,sender,task_id FROM inbox WHERE state='DISPATCHED' ORDER BY updated LIMIT ?",
                              (max(1, min(limit, 100)),)).fetchall()
        queued = []
        for row in rows:
            task = client.task(row["task_id"])
            if task.get("status") not in {"APPROVED", "FAILED", "BLOCKED", "CANCELLED"}:
                continue
            text = render_result(task)
            key = f"task-result:{row['sender']}:{row['message_id']}"
            self.queue_reply(key, row["sender"], text)
            with self.journal.connect() as db:
                db.execute("UPDATE inbox SET state='COMPLETED',result=?,updated=? WHERE message_id=?",
                           (json.dumps(task, ensure_ascii=False), time.time(), row["message_id"]))
            queued.append(key)
        return queued

    def queue_reply(self, key: str, recipient: str, text: str):
        if not key or not recipient or not text or len(text) > 32000:
            raise ValueError("Reply key, recipient and bounded text are required")
        with self.journal.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT recipient,text FROM outbox WHERE key=?", (key,)).fetchone()
            if prior and (prior["recipient"] != recipient or prior["text"] != text):
                raise ValueError("Idempotency key already used for different reply")
            db.execute("INSERT OR IGNORE INTO outbox(key,recipient,text,state,updated) VALUES (?,?,?,?,?)",
                       (key, recipient, text, "PENDING", time.time()))

    def deliver_reply(self, key: str):
        self.require("send_text")
        with self.journal.lock:
            with self.journal.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM outbox WHERE key=?", (key,)).fetchone()
                if not row:
                    raise KeyError(key)
                if row["state"] in {"SENT", "UNKNOWN", "SENDING"}:
                    # Unknown acknowledgement or interrupted send needs reconciliation,
                    # never an automatic duplicate message.
                    return dict(row)
                db.execute("UPDATE outbox SET state='SENDING',attempts=attempts+1,updated=? WHERE key=?",
                           (time.time(), key))
            try:
                remote_id = self.transport.send_text(row["recipient"], row["text"], idempotency_key=key)
                if not isinstance(remote_id, str) or not remote_id.strip():
                    raise RuntimeError("Transport returned no delivery acknowledgement ID")
                state, error = "SENT", None
            except RetryableSendError:
                state, error, remote_id = "PENDING", "ExplicitlyNotDelivered", None
            except Exception as exc:
                state, error, remote_id = "UNKNOWN", type(exc).__name__, None
            with self.journal.connect() as db:
                db.execute("UPDATE outbox SET state=?,remote_id=?,error=?,updated=? WHERE key=?",
                           (state, remote_id, error, time.time(), key))
                return dict(db.execute("SELECT * FROM outbox WHERE key=?", (key,)).fetchone())

    def reconcile_reply(self, key: str, *, evidence: str, remote_id: str | None = None,
                        confirmed_not_delivered: bool = False):
        """Operator/transport resolves an ambiguous send from actual remote evidence.

        This is deliberately explicit: a timeout is not proof of non-delivery.
        """
        if not evidence or len(evidence) > 2000 or bool(remote_id) == bool(confirmed_not_delivered):
            raise ValueError("Provide evidence and exactly one of remote acknowledgement or proved non-delivery")
        with self.journal.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM outbox WHERE key=?", (key,)).fetchone()
            if not row or row["state"] not in {"SENDING", "UNKNOWN"}:
                raise ValueError("Only an uncertain/interrupted send can be reconciled")
            state = "SENT" if remote_id else "PENDING"
            db.execute("UPDATE outbox SET state=?,remote_id=?,error=?,updated=? WHERE key=?",
                       (state, remote_id, "RECONCILED: " + evidence, time.time(), key))
            return dict(db.execute("SELECT * FROM outbox WHERE key=?", (key,)).fetchone())

    def resolve_contact(self, name: str):
        matches = {contact for label, ids in self.contacts.items() if label.casefold() == name.casefold() for contact in ids}
        matches &= self.allowed_contact_ids
        if not matches:
            raise LookupError("No allowed contact matches this name")
        if len(matches) > 1:
            raise AmbiguousContact("Multiple allowed contacts match; ask the owner for a contact ID")
        return next(iter(matches))

    def start_call(self, requester: str, name: str, *, approved: bool = False):
        if requester not in self.owner_ids or not approved:
            raise PermissionError("Owner authorization and explicit call approval are required")
        self.require("outgoing_call")
        contact = self.resolve_contact(name)
        call_id = self.transport.start_call(contact, introduction=AI_INTRODUCTION)
        if not call_id or not isinstance(call_id, str):
            raise RuntimeError("Transport did not return a real call ID")
        self.journal.call_event(call_id, "OUTGOING_REQUEST_ACCEPTED", "Transport returned call ID; answer and audio are not yet verified")
        return {"call_id": call_id, "status": "OUTGOING_REQUEST_ACCEPTED", "connected": False,
                "audio_tx_verified": False, "audio_rx_verified": False}

    def answer_call(self, call_id: str, caller_id: str, *, approved: bool = False):
        if caller_id not in self.allowed_contact_ids or not approved:
            raise PermissionError("Incoming caller is not approved")
        self.require("incoming_call")
        if self.transport.answer_call(call_id, introduction=AI_INTRODUCTION) is not True:
            raise RuntimeError("Transport did not acknowledge answering the call")
        self.journal.call_event(call_id, "ANSWER_REQUEST_ACCEPTED", "Transport acknowledgement; connected/audio require separate evidence")
        return {"call_id": call_id, "status": "ANSWER_REQUEST_ACCEPTED"}

    def record_call_evidence(self, call_id: str, state: str, evidence: str):
        if state not in {"CONNECTED", "AUDIO_TX_VERIFIED", "AUDIO_RX_VERIFIED", "ENDED", "FAILED"}:
            raise ValueError("Unknown call observation")
        if not evidence or len(evidence) > 2000:
            raise ValueError("Concrete bounded evidence from the transport/test operator is required")
        self.journal.call_event(call_id, state, evidence)

    def send_voice(self, recipient: str, pcm: bytes, *, idempotency_key: str):
        self.require("send_voice")
        if not pcm or len(pcm) % 2 or len(pcm) > 16000 * 2 * 300:
            raise ValueError("Voice must be bounded 16 kHz mono signed int16 PCM")
        remote_id = self.transport.send_voice(recipient, pcm, sample_rate=16000, idempotency_key=idempotency_key)
        if not remote_id:
            raise RuntimeError("No voice message acknowledgement returned")
        return remote_id
