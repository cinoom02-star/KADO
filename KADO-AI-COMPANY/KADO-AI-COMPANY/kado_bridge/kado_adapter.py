"""Authenticated REST integration; no assumptions about existing KADO internals."""
from __future__ import annotations

import time
import uuid
from typing import Any
from urllib.parse import urlsplit

import httpx


class KadoConnectionError(RuntimeError):
    pass


class KadoClient:
    def __init__(self, base_url: str, token: str, *, timeout: float = 20,
                 retries: int = 2, transport: httpx.BaseTransport | None = None):
        if not token or len(token) < 16:
            raise ValueError("A company API token of at least 16 characters is required")
        endpoint = urlsplit(base_url)
        if endpoint.scheme not in {"http", "https"} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError("Expected a plain HTTP(S) company base URL without credentials or query")
        if endpoint.scheme == "http" and endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Remote company connections require HTTPS")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.retries = max(0, min(retries, 5))
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout,
                                    headers={"Authorization": f"Bearer {token}"}, transport=transport)

    def __repr__(self):
        return f"KadoClient(base_url={self.base_url!r}, token=<redacted>)"

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        # GET and task creation (which always has an idempotency key) are retryable.
        retryable = method == "GET" or (path == "/api/tasks" and method == "POST")
        for attempt in range(self.retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
                if retryable and response.status_code in {429, 502, 503, 504} and attempt < self.retries:
                    try:
                        delay = min(5.0, max(0.0, float(response.headers.get("Retry-After", 0.25 * 2**attempt))))
                    except ValueError:
                        delay = 0.25 * 2**attempt
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.TransportError as exc:
                if not retryable or attempt >= self.retries:
                    # Do not leak request headers, URL credentials or a response body.
                    raise KadoConnectionError(f"Company connection failed: {type(exc).__name__}") from None
                time.sleep(0.1 * 2**attempt)
        raise KadoConnectionError("Company retry limit reached")

    def health(self):
        return self._request("GET", "/api/health")

    def agents(self):
        return self._request("GET", "/api/agents")

    def create_task(self, title: str, *, kind: str = "workspace_audit", input: dict | None = None,
                    idempotency_key: str | None = None):
        return self._request("POST", "/api/tasks", json={"title": title, "kind": kind,
                    "input": input or {}, "idempotency_key": idempotency_key or str(uuid.uuid4())})

    def task(self, task_id: str):
        return self._request("GET", f"/api/tasks/{task_id}")

    def events(self, after: int = 0):
        return self._request("GET", "/api/events", params={"after": after})

    def action(self, task_id: str, action: str):
        if action not in {"pause", "resume", "cancel", "retry", "approve", "reject"}:
            raise ValueError("Unsupported task action")
        return self._request("POST", f"/api/tasks/{task_id}/action", json={"action": action})
