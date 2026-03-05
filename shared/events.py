"""Observer Pattern — In-process event bus for inter-service communication.

Usage:
    # Register a handler
    @event_bus.on("employee.created")
    async def handle_employee_created(data: dict):
        ...

    # Emit an event
    await event_bus.emit("employee.created", {"employee_id": 1, "user_id": 5})

In monolith mode, events are dispatched in-process.
In proxy mode, each service can be extended to publish/subscribe via Redis Pub/Sub.
"""

from collections import defaultdict
from typing import Any, Callable, Coroutine

from shared.logging import get_logger

logger = get_logger(__name__)

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Simple async event bus implementing the Observer pattern."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event_name: str) -> Callable:
        """Decorator to register a handler for an event."""
        def decorator(fn: EventHandler) -> EventHandler:
            self._handlers[event_name].append(fn)
            return fn
        return decorator

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Programmatically subscribe a handler to an event."""
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Remove a handler from an event."""
        self._handlers[event_name] = [
            h for h in self._handlers[event_name] if h is not handler
        ]

    async def emit(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event, calling all registered handlers."""
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            return

        logger.info("event_emitted", event=event_name, handler_count=len(handlers))
        for handler in handlers:
            try:
                await handler(data or {})
            except Exception:
                logger.error(
                    "event_handler_failed",
                    event=event_name,
                    handler=handler.__qualname__,
                    exc_info=True,
                )

    @property
    def registered_events(self) -> list[str]:
        """List all events that have at least one handler."""
        return [k for k, v in self._handlers.items() if v]


# Global singleton
event_bus = EventBus()
