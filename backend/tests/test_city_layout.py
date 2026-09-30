from collections import Counter
from itertools import pairwise

from generation.fixture_town import build_fixture
from generation.validators import validate_place_layout
from simulation.routing import road_route
from simulation.tick import STATIONS, _rail_position


def test_city_households_and_connected_building_access():
    world = build_fixture(7341)
    assert len(world["people"]) == 32
    sizes = Counter(len(household["member_ids"]) for household in world["households"])
    assert sizes[1] >= 3 and sizes[3] and sizes[4] >= 2
    validate_place_layout(world["places"])
    for place in world["places"]:
        entrance = {"x": place["position"]["x"], "y": place["position"]["y"] + 48}
        route = road_route(world["roads"], {"x": 365, "y": 350}, entrance)
        assert route[-1] == entrance
    assert sum(place.get("house_style") == "large" for place in world["places"]) >= 3


def test_winding_rail_loop_and_stations_share_geometry():
    track = build_fixture(7341)["trains"][0]["track"]
    assert (track[0]["x"], track[0]["y"]) == (track[-1]["x"], track[-1]["y"])
    assert len(track) > 12
    assert any(point["x"] < 100 for point in track)
    assert any(point["x"] == 390 and point["y"] == 360 for point in track)
    assert all(b["distance"] > a["distance"] for a, b in pairwise(track))
    for station in STATIONS.values():
        assert _rail_position(station["distance"]) == station["position"]


def test_streets_have_no_duplicate_or_close_parallel_segments():
    world = build_fixture(7341)
    streets = [road for road in world["roads"] if not road["id"].startswith("road:access-")]
    segments = [segment for road in streets for segment in pairwise(road["points"])]
    for index, (a, b) in enumerate(segments):
        for c, d in segments[index + 1:]:
            if a[1] == b[1] and c[1] == d[1]:
                overlap = min(b[0], d[0]) > max(a[0], c[0])
                assert not overlap or abs(a[1] - c[1]) >= 60
            if a[0] == b[0] and c[0] == d[0]:
                overlap = min(b[1], d[1]) > max(a[1], c[1])
                assert not overlap or abs(a[0] - c[0]) >= 60
    assert world["paths"] == []


def test_saved_city_cleanup_preserves_residents_and_connects_south_entrances():
    from simulation.versions import migrate_snapshot

    original = build_fixture(7341)
    original.pop("city_layout_version")
    original["roads"].append({"id": "road:duplicate", "points": [[45, 350], [1140, 350]]})
    original["paths"] = [{"id": "path:overlap", "points": [[365, 170], [365, 520]]}]
    migrated = migrate_snapshot(original)
    assert migrated["people"] == original["people"]
    assert migrated["clock"] == original["clock"]
    assert migrated["paths"] == []
    assert original["paths"]  # Loading does not mutate the durable save.
    for place in migrated["places"]:
        entrance = place["entrance"]
        assert entrance == {"x": place["position"]["x"], "y": place["position"]["y"] + 48}
        access = next(road for road in migrated["roads"] if road["id"] == f"road:access-{place['id']}")
        assert access["points"][0][0] == entrance["x"]
        assert access["points"][0][1] >= entrance["y"]
        route = road_route(migrated["roads"], {"x": 365, "y": 350}, entrance)
        assert route[-1] == entrance
    assert migrate_snapshot(migrated) == migrated
