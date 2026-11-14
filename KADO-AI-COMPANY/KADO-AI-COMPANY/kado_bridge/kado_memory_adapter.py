"""Read company memory; never import or modify existing KADO memory automatically."""
from .kado_adapter import KadoClient


class KadoMemoryAdapter:
    def __init__(self, client: KadoClient):
        self.client = client

    def read(self, scope: str = "company", scope_id: str | None = None):
        params = {"scope": scope}
        if scope_id:
            params["scope_id"] = scope_id
        return self.client._request("GET", "/api/memory", params=params)
