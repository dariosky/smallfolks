"""Commit-driven world subscriptions with bounded queues and sparse JSON patches."""

import asyncio
from copy import deepcopy
from threading import Lock


def world_patch(previous: dict, current: dict) -> list[dict]:
    operations = []

    def diff(old, new, path):
        if old == new:
            return
        if isinstance(old, dict) and isinstance(new, dict):
            for key in old.keys() - new.keys():
                operations.append({"path": [*path, key], "deleted": True})
            for key, value in new.items():
                if key not in old:
                    operations.append({"path": [*path, key], "value": value})
                else:
                    diff(old[key], value, [*path, key])
        elif (
            isinstance(old, list)
            and isinstance(new, list)
            and len(old) == len(new)
            and all(
                isinstance(a, dict)
                and isinstance(b, dict)
                and a.get("id") == b.get("id")
                for a, b in zip(old, new)
            )
        ):
            for index, (a, b) in enumerate(zip(old, new)):
                diff(a, b, [*path, index])
        else:
            operations.append({"path": path, "value": new})

    diff(previous, current, [])
    return operations


class WorldSubscription:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
        self.active = True

    def offer(self, state: dict) -> None:
        if not self.active:
            return
        if self.queue.full():
            self.queue.get_nowait()
        self.queue.put_nowait(state)


class WorldStreams:
    def __init__(self):
        self._lock = Lock()
        self._subscribers: dict[str, set[WorldSubscription]] = {}

    def subscribe(
        self, world_id: str, loop: asyncio.AbstractEventLoop
    ) -> WorldSubscription:
        subscription = WorldSubscription(loop)
        with self._lock:
            self._subscribers.setdefault(world_id, set()).add(subscription)
        return subscription

    def unsubscribe(self, world_id: str, subscription: WorldSubscription) -> None:
        with self._lock:
            subscription.active = False
            subscribers = self._subscribers.get(world_id)
            if subscribers is not None:
                subscribers.discard(subscription)
                if not subscribers:
                    del self._subscribers[world_id]

    def publish(self, state: dict) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers.get(state["id"], ()))
        if not subscribers:
            return
        # Isolate queued states from callers; share one immutable copy across clients.
        snapshot = deepcopy(state)
        for subscription in subscribers:
            if not subscription.loop.is_closed():
                subscription.loop.call_soon_threadsafe(subscription.offer, snapshot)


world_streams = WorldStreams()
