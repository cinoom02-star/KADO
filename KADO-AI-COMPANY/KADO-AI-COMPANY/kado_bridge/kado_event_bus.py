from __future__ import annotations
import asyncio
import json
from collections import defaultdict
from typing import Any, Callable


class LocalEventBus:
    """In-process notifications only. Durable history remains in the company DB."""
    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[dict], Any]):
        self._handlers[event_type].append(handler)
        def unsubscribe():
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
        return unsubscribe

    async def publish(self, event: dict):
        errors = []
        for handler in list(self._handlers.get(event.get("type"), [])) + list(self._handlers.get("*", [])):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                errors.append(type(exc).__name__)
        return errors


async def websocket_events(base_url: str, token: str, *, after: int = 0, reconnects: int = 5):
    """Resume by event ID; token is sent in first frame, never a URL query."""
    try:
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed, InvalidHandshake
    except ImportError as exc:
        raise RuntimeError("WebSocket SDK requires the optional websockets package") from exc
    url = base_url.rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/api/ws/events"
    cursor, attempt = after, 0
    while True:
        try:
            async with connect(url, open_timeout=10, max_size=2**20) as socket:
                await socket.send(json.dumps({"token": token, "after": cursor}))
                async for raw in socket:
                    message = json.loads(raw)
                    if isinstance(message, dict) and message.get("type") in {"heartbeat", "connected"}:
                        continue
                    events = message if isinstance(message, list) else message.get("events", [message])
                    for event in events:
                        event_id = event.get("id", 0)
                        if isinstance(event_id, int) and event_id > cursor:
                            cursor = event_id
                            yield event
            # A gracefully closed connection also needs a bounded reconnect.
            attempt += 1
            if attempt > reconnects:
                raise RuntimeError("Event stream reconnect limit reached")
            await asyncio.sleep(min(5, 0.2 * 2**attempt))
        except (OSError, TimeoutError, ConnectionClosed, InvalidHandshake) as exc:
            attempt += 1
            if attempt > reconnects:
                raise RuntimeError("Event stream reconnect limit reached") from exc
            await asyncio.sleep(min(5, 0.2 * 2**attempt))
