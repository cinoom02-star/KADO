"""KADO's tool-calling boundary: task submission is owned by the existing CEO."""
from __future__ import annotations
from .kado_adapter import KadoClient


class KadoAgentGateway:
    def __init__(self, client: KadoClient):
        self.client = client

    @staticmethod
    def tool_schema():
        return {"type": "function", "function": {
            "name": "company_submit_task", "description": "Submit a real task to KADO's company sidecar.",
            "parameters": {"type": "object", "properties": {
                "title": {"type": "string"}, "kind": {"type": "string", "enum": ["workspace_audit", "llm_task"]},
                "input": {"type": "object"}, "idempotency_key": {"type": "string"}},
                "required": ["title", "kind", "input"], "additionalProperties": False}}}

    def submit(self, *, title: str, kind: str, input: dict, idempotency_key: str | None = None):
        return self.client.create_task(title, kind=kind, input=input, idempotency_key=idempotency_key)
