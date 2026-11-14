"""Sidecar SDK: existing KADO remains the CEO; this package does not replace it."""
from .kado_adapter import KadoClient, KadoConnectionError
from .kado_agent_gateway import KadoAgentGateway
from .kado_task_dispatcher import KadoTaskDispatcher
from .kado_event_bus import LocalEventBus

__all__ = ["KadoClient", "KadoConnectionError", "KadoAgentGateway", "KadoTaskDispatcher", "LocalEventBus"]
