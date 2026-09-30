from generation.fixture_town import build_fixture
from simulation.tick import _car_journey
from simulation.versions import migrate_snapshot


def test_vehicle_households_have_large_homes_and_park_in_driveways():
    world = build_fixture(7341)
    places = {place["id"]: place for place in world["places"]}
    for vehicle in world["vehicles"]:
        household = next(h for h in world["households"] if vehicle["owner_id"] in h["member_ids"])
        home = places[household["home_place_id"]]
        assert home["house_style"] == "large"
        assert vehicle["position"] == home["driveway"]["parking_position"]
        assert vehicle["parking_place_id"] == home["id"]
        person = next(p for p in world["people"] if p["id"] == vehicle["owner_id"])
        person["position"] = {"x": 1000, "y": 550}
        vehicle["position"] = {"x": 1000, "y": 534}
        vehicle["parking_place_id"] = "place:clinic"
        journey = _car_journey(world, person, home)
        assert journey is not None
        assert journey["parking_position"] == home["driveway"]["parking_position"]
    assert "driveway" not in places["place:rowan-1"]


def test_existing_save_gets_driveways_without_moving_cars_away_from_home():
    world = build_fixture(7341)
    for place in world["places"]:
        place.pop("driveway", None)
        place.pop("house_style", None)
    vehicle = world["vehicles"][0]
    vehicle["position"] = {"x": 1000, "y": 534}
    vehicle["parking_place_id"] = "place:clinic"
    migrated = migrate_snapshot(world)
    assert migrated["vehicles"][0]["position"] == vehicle["position"]
    assert any(place.get("driveway") for place in migrated["places"])
    assert all("driveway" not in place for place in world["places"])
