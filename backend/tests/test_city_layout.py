from collections import Counter
from itertools import pairwise

from generation.fixture_town import build_fixture
from generation.validators import validate_place_layout
from simulation.routing import road_route
from simulation.tick import STATIONS, _rail_position


def test_city_households_and_connected_building_access():
    world = build_fixture(7341)
    assert len(world["people"]) == 30
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
