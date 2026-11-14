"""Durable, bounded task workers with real handoffs, evidence and independent review."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .providers import ProviderUnavailable, generate
from .registry import AGENT_BY_ID, require_permission
from .tools import ToolLimit, WorkspaceTools

ACTIVE = {"PLANNING", "IN_PROGRESS", "REVIEW", "REVISION_REQUIRED"}
TERMINAL = {"APPROVED", "FAILED", "BLOCKED", "CANCELLED"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class HaltTask(Exception):
    """A persisted pause/cancellation is control flow, not a successful result."""


class ReviewRejected(RuntimeError):
    def __init__(self, review: dict):
        self.review = review
        super().__init__("Bağımsız denetim dosya kanıtlarını reddetti")


class Engine:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.tools = WorkspaceTools(settings.workspace_root, settings.data_dir,
                                    max_files=getattr(settings, "max_files", 500),
                                    max_file_bytes=getattr(settings, "max_file_bytes", 2 * 1024 * 1024))
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._active: dict[str, asyncio.Task] = {}
        # Task-based execution: the workers share models. Hardware is not assumed.
        self.concurrency = max(1, min(int(getattr(settings, "worker_concurrency", 1)), 4))

    async def start(self) -> None:
        if self._running:
            return
        self.store.recover_tasks()
        self._running = True
        self._workers = [asyncio.create_task(self._worker(), name=f"company-worker-{i}") for i in range(self.concurrency)]

    async def stop(self) -> None:
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._active.clear()

    def status(self) -> dict:
        return {"running": self._running, "worker_concurrency": self.concurrency,
                "healthy_workers": sum(not worker.done() for worker in self._workers),
                "active_task_ids": sorted(self._active),
                "kill_switch": bool(self.store.get_setting("kill_switch", False)),
                "execution_mode": "bounded_persistent_queue",
                "supported_workflows": ["workspace_audit", "llm_task"]}

    async def set_kill_switch(self, enabled: bool) -> dict:
        self.store.set_setting("kill_switch", bool(enabled))
        if enabled:
            for task_id in list(self._active):
                task = self.store.get_task(task_id)
                if task and task["status"] in ACTIVE:
                    await self.action(task_id, "pause")
        return self.status()

    async def action(self, task_id: str, action: str) -> dict:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(task_id)
        current = task["status"]
        action = action.lower()
        if action == "cancel":
            if current in TERMINAL:
                raise ValueError(f"{current} durumundaki görev iptal edilemez")
            new = "CANCELLED"
        elif action == "pause":
            if current not in ACTIVE | {"PENDING"}:
                raise ValueError(f"{current} durumundaki görev duraklatılamaz")
            new = "PAUSED"
        elif action == "resume":
            if current != "PAUSED":
                raise ValueError("Yalnızca PAUSED görevi devam ettirilebilir")
            if self.store.get_setting("kill_switch", False):
                raise ValueError("Kill switch açık; önce kapatın")
            new = "REVIEW" if task.get("paused_from") == "REVIEW" and (task.get("result") or {}).get("human_review_required") else "PENDING"
        elif action in {"approve", "reject"}:
            if current != "REVIEW" or not (task.get("result") or {}).get("human_review_required"):
                raise ValueError("İnsan kararı yalnızca insan incelemesi bekleyen REVIEW görevi için verilebilir")
            if action == "approve":
                new = "APPROVED"
                self.store.update_task(task_id, owner_decision={"decision": "approved", "at": utcnow(),
                    "note": "İçerik sahibi tarafından kabul edildi; otomatik olgusal doğrulama iddiası değildir"})
            else:
                new = "REVISION_REQUIRED" if int(task.get("retry_count", 0)) < int(task.get("max_retries", 2)) else "FAILED"
                self.store.update_task(task_id, error="İçerik sahibi çıktıyı reddetti",
                    revision={"reason": "İçerik sahibi çıktıyı reddetti", "agent_id": task.get("assigned_agent_id"),
                              "suggestion": "Girdiyi gözden geçirin; yeniden deneme ayrı ve bütçeyle sınırlıdır"})
                self.store.add_event(task_id, "revision.requested", {"reason": "owner_rejected", "status": new})
        elif action == "retry":
            if current not in {"FAILED", "BLOCKED", "REVISION_REQUIRED"}:
                raise ValueError("Yalnızca başarısız/engelli görev yeniden denenebilir")
            if int(task.get("retry_count", 0)) >= int(task.get("max_retries", getattr(self.settings, "max_retries", 2))):
                raise ValueError("Yeniden deneme sınırı doldu; girdiyi düzelterek yeni görev oluşturun")
            self.store.update_task(task_id, retry_count=int(task.get("retry_count", 0)) + 1)
            new = "PENDING"
        else:
            raise ValueError("Desteklenen eylemler: pause, resume, cancel, retry, approve, reject")
        updates: dict[str, Any] = {"status": new}
        if new == "PENDING":
            updates.update(error=None, result=None, finished_at=None)
        elif new == "CANCELLED":
            updates["finished_at"] = utcnow()
        elif new in {"APPROVED", "FAILED"}:
            updates["finished_at"] = utcnow()
        if action == "pause":
            updates["paused_from"] = current
        elif action == "resume":
            updates["paused_from"] = None
        self.store.update_task(task_id, **updates)
        self.store.add_event(task_id, "task.control", {"action": action, "from": current, "to": new})
        runner = self._active.get(task_id)
        if runner and not runner.done():
            runner.cancel()
        return self.store.get_task(task_id)

    async def _worker(self) -> None:
        while self._running:
            if self.store.get_setting("kill_switch", False):
                await asyncio.sleep(0.15)
                continue
            task = self.store.claim_task()
            if task is None:
                await asyncio.sleep(0.1)
                continue
            task_id = task["id"]
            runner = asyncio.create_task(self._run(task), name=f"task-{task_id}")
            self._active[task_id] = runner
            try:
                await runner
            except asyncio.CancelledError:
                if not self._running:
                    raise
            finally:
                self._active.pop(task_id, None)

    async def _checkpoint(self, task_id: str) -> None:
        await asyncio.sleep(0)  # Let pause/cancel/kill requests run between bounded I/O steps.
        task = self.store.get_task(task_id)
        if task is None or task["status"] in {"PAUSED", "CANCELLED"}:
            raise HaltTask()
        if self.store.get_setting("kill_switch", False):
            self.store.update_task(task_id, status="PAUSED")
            raise HaltTask()

    def _status(self, task_id: str, status: str, **fields) -> None:
        self.store.update_task(task_id, status=status, **fields)
        self.store.add_event(task_id, "task.status", {"status": status})

    def _assign(self, task_id: str, from_id: str, to_id: str, purpose: str) -> None:
        if from_id not in AGENT_BY_ID or to_id not in AGENT_BY_ID:
            raise ValueError("Bilinmeyen ajan")
        self.store.update_task(task_id, assigned_agent_id=to_id)
        self.store.add_event(task_id, "task.assigned", {"from_agent_id": from_id, "to_agent_id": to_id,
                             "purpose": purpose}, agent_id=to_id)

    async def _tool(self, task_id: str, agent_id: str, name: str, args: dict, operation):
        require_permission(agent_id, name)
        self.store.add_event(task_id, "tool.started", {"name": name, "args": args}, agent_id=agent_id)
        try:
            result = await operation()
        except BaseException as exc:
            detail = "Durduruldu" if isinstance(exc, (asyncio.CancelledError, HaltTask)) else str(exc)[:500]
            self.store.add_tool_call(task_id, agent_id, name, args, {"error": detail}, "FAILED")
            self.store.add_event(task_id, "tool.completed", {"name": name, "status": "FAILED", "error": detail}, agent_id=agent_id)
            raise
        # Persist full deterministic evidence. LLM text is stored in its task response artifact.
        self.store.add_tool_call(task_id, agent_id, name, args, result, "SUCCEEDED")
        self.store.add_event(task_id, "tool.completed", {"name": name, "status": "SUCCEEDED"}, agent_id=agent_id)
        return result

    async def _run(self, task: dict) -> None:
        task_id = task["id"]
        self.store.update_task(task_id, started_at=utcnow())
        self.store.add_event(task_id, "task.planning", {"kind": task.get("type", task.get("kind")),
                             "mode": "explicit_workflow_template", "note": "CEO KADO'nun verdiği görev; yeni CEO modeli oluşturulmaz"}, agent_id="kado")
        try:
            timeout = max(1.0, min(float(task.get("timeout_seconds") or getattr(self.settings, "task_timeout", 120)), 1800.0))
            await asyncio.wait_for(self._execute(task), timeout=timeout)
        except HaltTask:
            return
        except asyncio.CancelledError:
            raise
        except (PermissionError, FileNotFoundError, ToolLimit, ProviderUnavailable, ValueError) as exc:
            self._status(task_id, "BLOCKED", error=str(exc)[:1000], finished_at=utcnow())
            self.store.add_event(task_id, "task.blocked", {"reason": str(exc)[:1000]})
        except Exception as exc:
            current = self.store.get_task(task_id)
            retries = int(current.get("retry_count", 0))
            limit = int(current.get("max_retries", getattr(self.settings, "max_retries", 2)))
            reason = "Görev zaman aşımı" if isinstance(exc, TimeoutError) else f"{type(exc).__name__}: {str(exc)[:500]}"
            review = exc.review if isinstance(exc, ReviewRejected) else {"passed": False, "reason": reason}
            if retries < limit:
                self._status(task_id, "REVISION_REQUIRED", error=reason, review=review,
                             revision={"reason": reason, "agent_id": current.get("assigned_agent_id"),
                                       "suggestion": "Girdileri ve dosya kararlılığını doğrulayıp kanıtları yeniden üretin", "attempt": retries + 1})
                self.store.add_event(task_id, "revision.requested", {"reason": reason, "attempt": retries + 1,
                                     "max_retries": limit}, agent_id="quality_auditor")
                self.store.update_task(task_id, retry_count=retries + 1, status="PENDING")
            else:
                self._status(task_id, "FAILED", error=reason, review=review, finished_at=utcnow())
                self.store.add_event(task_id, "task.failed", {"reason": reason, "attempts": retries + 1})

    async def _execute(self, task: dict) -> None:
        task_id = task["id"]
        await self._checkpoint(task_id)
        kind = task.get("type", task.get("kind", ""))
        if kind == "workspace_audit":
            await self._workspace_audit(task)
        elif kind == "llm_task":
            await self._llm_task(task)
        else:
            raise ValueError(f"Çalıştırılabilir iş akışı bulunmuyor: {kind}")

    async def _workspace_audit(self, task: dict) -> None:
        task_id = task["id"]
        relative = task.get("input", {}).get("path", ".")
        self.store.update_task(task_id,
            acceptance_criteria=["Yalnızca izinli dosya alanı okunur", "Gerçek SHA-256 ve boyut kanıtı üretilir",
                                 "QA ve bağımsız denetçi kanıtları yeniden hesaplar", "Hariç tutulan dosyalar açıklanır"],
            test_plan=["JSON şema kontrolü", "Dosya yolu/kapsam kontrolü", "Her dosyanın hash ve boyutunu yeniden hesapla",
                       "Dosya sayısı ve toplam baytları karşılaştır", "Hariç tutulanları doğrula"])
        self._assign(task_id, "kado", "cto", "Dosya envanteri işini yazılım departmanına aktar")
        self._assign(task_id, "cto", "senior_fullstack", "İzinli proje dosyalarının gerçek envanterini üret")
        self._status(task_id, "IN_PROGRESS")
        checkpoint = lambda: self._checkpoint(task_id)
        report = await self._tool(task_id, "senior_fullstack", "workspace_inventory", {"path": relative},
                                  lambda: self.tools.inventory(relative, checkpoint))

        async def write_report():
            await checkpoint()
            return self.tools.write_json(task_id, report)

        artifact = await self._tool(task_id, "senior_fullstack", "write_report", {"name": "report.json"}, write_report)
        self._assign(task_id, "cto", "qa_engineer", "Raporu diskteki dosyalarla karşılaştır")
        self._status(task_id, "REVIEW")
        qa = await self._tool(task_id, "qa_engineer", "verify_report", {"task_id": task_id},
                              lambda: self.tools.verify(task_id, relative, checkpoint))
        self.tools.write_json(task_id, qa, "qa.json")
        self.store.add_event(task_id, "review.completed", {"stage": "qa", **qa}, agent_id="qa_engineer")
        if not qa["passed"]:
            raise ReviewRejected(qa)
        self._assign(task_id, "kado", "coo", "Operasyon departmanından bağımsız son denetim iste")
        self._assign(task_id, "coo", "quality_auditor", "QA sonucundan bağımsız dosya doğrulaması ve son denetim")
        audit = await self._tool(task_id, "quality_auditor", "audit_report", {"task_id": task_id},
                                 lambda: self.tools.verify(task_id, relative, checkpoint))
        self.tools.write_json(task_id, audit, "audit.json")
        self.store.add_event(task_id, "review.completed", {"stage": "audit", **audit}, agent_id="quality_auditor")
        if not audit["passed"]:
            raise ReviewRejected(audit)
        await checkpoint()
        result = {"report": artifact, "qa": qa, "audit": audit,
                  "summary": f"{report['file_count']} dosya / {report['total_bytes']} bayt için SHA-256 kanıtları doğrulandı; {len(report['excluded'])} öğe kapsam dışı.",
                  "scope_note": report["scope_note"]}
        self.store.add_memory("task", task_id, {"summary": result["summary"], "evidence": artifact}, task_id)
        self.store.add_memory("agent", "quality_auditor", {"task_id": task_id, "verified_report_sha256": audit["report_sha256"]}, task_id)
        self._status(task_id, "APPROVED", result=result, review=audit, error=None, assigned_agent_id="kado", finished_at=utcnow())
        self.store.add_event(task_id, "task.completed", {"summary": result["summary"], "report_sha256": artifact["sha256"]}, agent_id="kado")

    async def _llm_task(self, task: dict) -> None:
        task_id = task["id"]
        data = task.get("input", {})
        agent_id = data.get("agent_id", "deep_researcher")
        require_permission(agent_id, "llm_generate")
        agent = AGENT_BY_ID[agent_id]
        manager_id = agent["manager_id"]
        prompt = data.get("prompt", task.get("title", ""))
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
            raise ValueError("Üretim girdisi 1–20000 karakter olmalıdır")
        default_provider = getattr(self.settings, "model_provider", "unconfigured")
        provider = data.get("provider") or (default_provider if default_provider in {"ollama", "gemini"} else "ollama")
        self.store.update_task(task_id,
            acceptance_criteria=["Yapılandırılmış sağlayıcıdan boş olmayan gerçek yanıt", "Sağlayıcı/model/kullanım metaverisi ve SHA-256 kanıtı"],
            test_plan=["HTTP ve yanıt şeması kontrolü", "Yanıt dosyası hash doğrulaması", "İçerik kalitesi için insan incelemesi"])
        self._assign(task_id, "kado", manager_id, "Seçilen uzman departmanına üretim görevi aktar")
        self._assign(task_id, manager_id, agent_id, "Yapılandırılmış sağlayıcıdan gerçek metin çıktısı üret")
        self._status(task_id, "IN_PROGRESS")
        response = await self._tool(task_id, agent_id, "llm_generate", {"provider": provider, "prompt_chars": len(prompt)},
                                    lambda: generate(self.settings, prompt, agent["name"], provider))
        await self._checkpoint(task_id)
        artifact = self.tools.write_json(task_id, response, "response.json")
        saved = Path(artifact["path"]).read_bytes()
        review = {"passed": hashlib.sha256(saved).hexdigest() == artifact["sha256"],
                  "checks": [{"name": "response_nonempty", "passed": bool(response["text"].strip())},
                             {"name": "response_artifact_hash", "passed": hashlib.sha256(saved).hexdigest() == artifact["sha256"]}],
                  "scope_note": "Teknik teslim kontrolü; doğruluk, kaynaklar ve içerik kalitesi insan değerlendirmesi gerektirir."}
        self._status(task_id, "REVIEW", result={"response": response, "artifact": artifact, "human_review_required": True}, review=review)
        self.store.add_event(task_id, "review.required", review, agent_id="quality_auditor")
