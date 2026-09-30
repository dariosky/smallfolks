import asyncio
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import create_app
from services.world_stream import WorldStreams, world_patch
from services.worlds import tick_running_worlds


def apply_patch(state, operations):
    result = deepcopy(state)
    for operation in operations:
        parent = result
        for key in operation["path"][:-1]:
            parent = parent[key]
        key = operation["path"][-1]
        if operation.get("deleted"):
            del parent[key]
        else:
            parent[key] = operation["value"]
    return result


def test_sparse_patch_handles_fields_routes_additions_removals_and_reordering():
    old = {
        "revision": 1,
        "people": [
            {"id": "a", "position": {"x": 1, "y": 2}, "route": [1, 2]},
            {"id": "b"},
        ],
        "old": True,
    }
    new = {
        "revision": 2,
        "people": [
            {"id": "a", "position": {"x": 3, "y": 2}, "route": None},
            {"id": "b"},
        ],
        "new": True,
    }
    operations = world_patch(old, new)
    assert apply_patch(old, operations) == new
    assert {"path": ["people", 0, "position", "x"], "value": 3} in operations
    assert not any(op["path"] == ["people"] for op in operations)
    assert world_patch(new, new) == []
    for people in [new["people"][::-1], [], [*new["people"], {"id": "c"}]]:
        changed = {**new, "people": people}
        assert apply_patch(new, world_patch(new, changed)) == changed


def test_subscriptions_coalesce_slow_clients_and_isolate_worlds():
    async def scenario():
        streams = WorldStreams()
        subscription = streams.subscribe("one", asyncio.get_running_loop())
        other = streams.subscribe("two", asyncio.get_running_loop())
        for revision in range(10):
            streams.publish({"id": "one", "revision": revision})
        await asyncio.sleep(0)
        assert subscription.queue.qsize() == 1
        assert (await subscription.queue.get())["revision"] == 9
        assert other.queue.empty()
        streams.unsubscribe("one", subscription)
        streams.publish({"id": "one", "revision": 10})
        await asyncio.sleep(0)
        assert subscription.queue.empty()
        streams.unsubscribe("two", other)

    asyncio.run(scenario())


def test_websocket_streams_commits_to_multiple_clients_and_resyncs_on_reconnect():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 98765}).json()
        url = f"/api/worlds/{world['id']}/stream"
        with (
            client.websocket_connect(url) as first,
            client.websocket_connect(url) as second,
        ):
            assert first.receive_json() == {"type": "snapshot", "world": world}
            assert second.receive_json()["world"] == world
            changed = client.post(
                f"/api/worlds/{world['id']}/run", json={"running": True, "speed": 2}
            ).json()
            patch = first.receive_json()
            assert patch["type"] == "patch"
            assert patch["base_revision"] == world["revision"]
            assert patch["revision"] == changed["revision"]
            assert apply_patch(world, patch["operations"]) == changed
            assert second.receive_json() == patch
            assert len(json.dumps(patch)) < len(json.dumps(changed)) / 10
            tick_running_worlds()
            tick_patch = first.receive_json()
            ticked = client.get(f"/api/worlds/{world['id']}").json()
            assert apply_patch(changed, tick_patch["operations"]) == ticked
            assert second.receive_json() == tick_patch
        with client.websocket_connect(url) as resumed:
            assert resumed.receive_json()["world"] == ticked


def test_stream_rejects_unknown_world():
    with (
        TestClient(create_app()) as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/worlds/missing/stream"),
    ):
        pass
