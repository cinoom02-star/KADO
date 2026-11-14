from __future__ import annotations
import time
from .kado_adapter import KadoClient


class KadoTaskDispatcher:
    TERMINAL = {"APPROVED", "FAILED", "BLOCKED", "CANCELLED"}

    def __init__(self, client: KadoClient):
        self.client = client

    def wait(self, task_id: str, timeout: float = 120, poll_interval: float = 0.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            task = self.client.task(task_id)
            if task["status"] in self.TERMINAL or (task["status"] == "REVIEW" and (task.get("result") or {}).get("human_review_required")):
                return task
            time.sleep(min(max(0.1, poll_interval), max(0, deadline - time.monotonic())))
        raise TimeoutError(f"Task still running: {task_id}; task was not cancelled")
