from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List


EventHandler = Callable[[dict[str, Any]], None]


class AgentBus:
    _instance: "AgentBus | None" = None

    def __new__(cls) -> "AgentBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = defaultdict(list)
        return cls._instance

    def publish(self, event: str, data: dict[str, Any]) -> None:
        for handler in list(self._subscribers[str(event or "").strip()]):
            try:
                handler(dict(data))
            except Exception:
                continue

    def subscribe(self, event: str, handler: EventHandler) -> None:
        event_name = str(event or "").strip()
        if not event_name:
            raise ValueError("event is required")
        if handler not in self._subscribers[event_name]:
            self._subscribers[event_name].append(handler)

    def request(self, from_agent: str, to_agent: str, task: str, data: dict[str, Any] | None = None) -> Any:
        from agents.agent_registry import AgentRegistry

        payload = dict(data or {})
        payload.setdefault("from_agent", from_agent)
        payload.setdefault("task", task)
        return AgentRegistry().call(to_agent, task, payload)


agent_bus = AgentBus()
