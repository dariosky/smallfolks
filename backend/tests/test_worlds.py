from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import create_app
from generation.fixture_town import build_fixture
from simulation.tick import advance


def test_fixture_world_can_advance_and_reload():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 90111}).json()
        world_id = world["id"]
        expected_clock = (
            datetime.fromisoformat(world["clock"]) + timedelta(minutes=30)
        ).isoformat(timespec="minutes")
        advanced = client.post(f"/api/worlds/{world_id}/advance", json={"minutes": 30})
        assert advanced.status_code == 200
        reloaded = client.get(f"/api/worlds/{world_id}")
        assert reloaded.status_code == 200
        assert reloaded.json()["clock"] == expected_clock
        assert len(reloaded.json()["people"]) == 10
        index = client.get("/api/worlds")
        assert index.status_code == 200
        assert any(item["id"] == world_id for item in index.json())


def test_render_state_and_inspector_are_available():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 222}).json()
        render = client.get(f"/api/worlds/{world['id']}/render-state")
        inspector = client.get(f"/api/worlds/{world['id']}/entities/person:elena")
        assert len(render.json()["entities"]) == 13
        assert inspector.json()["name"] == "Elena Rossi"


def test_backend_serves_the_built_frontend():
    with TestClient(create_app()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<div id=\"root\"></div>" in response.text


def test_commute_is_a_timed_walking_activity():
    world = build_fixture(77)
    marco = next(person for person in world["people"] if person["id"] == "person:marco")
    starting_position = dict(marco["position"])
    advanced = advance(world, 10)
    marco = next(person for person in advanced["people"] if person["id"] == "person:marco")
    assert marco["activity"].startswith("Walking to") or "Folk Loop" in marco["activity"]
    assert marco["position"] != starting_position
    assert len(marco["route"]) > 2
