from __future__ import annotations
import time
from .kado_adapter import KadoClient


class KadoHealthMonitor:
    def __init__(self, client: KadoClient):
        self.client = client

    def check(self):
        started = time.monotonic()
        try:
            health = self.client.health()
            return {"reachable": True, "latency_ms": round((time.monotonic()-started)*1000, 2),
                    "health": health}
        except Exception as exc:
            return {"reachable": False, "error": type(exc).__name__}
