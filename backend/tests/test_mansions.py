from copy import deepcopy
from datetime import datetime
from itertools import pairwise

from generation.fixture_town import build_fixture
from generation.validators import validate_place_layout
from simulation.housing import home_parking_point
from simulation.mansions import MANSION_PRICE
from simulation.prosperity import (
    CASH_RESERVE,
    buy_car,
    buy_house,
    car_purchase_available,
    consider_prosperity,
    refresh_aspiration,
)
from simulation.routing import nearest_road_point, road_route
from simulation.tick import _car_journey, _position_at, _residential_walk_route
from simulation.versions import migrate_snapshot


def resident(world, slug):
    return next(person for person in world["people"] if person["id"] == f"person:{slug}")


def villa(world):
    return next(place for place in world["places"] if place.get("house_style") == "mansion")


def test_villas_have_room_for_gardens_and_connected_gates_and_two_parking_bays():
    world = build_fixture(7341)
    validate_place_layout(world["places"])
    assert world["map_size"]["height"] >= 1450
    for home in (place for place in world["places"] if place.get("house_style") == "mansion"):
        assert home["owner_household_id"] is None
        assert home["sale_price_cents"] == MANSION_PRICE
        slots = home["driveway"]["parking_positions"]
        assert len(slots) == 2 and slots[0] != slots[1]
        for slot in slots:
            assert nearest_road_point(world["roads"], slot) == slot
            route = road_route(world["roads"], {"x": 365, "y": 350}, slot)
            assert route[-1] == slot
            assert any(a["x"] == b["x"] == home["estate_gate"]["x"]
                       and min(a["y"], b["y"]) <= home["estate_gate"]["y"] <= max(a["y"], b["y"])
                       for a, b in pairwise(route))


def test_existing_city_receives_villas_without_resetting_money_or_positions():
    original = build_fixture(7341)
    original.pop("mansion_district_version")
    original["places"] = [place for place in original["places"] if place.get("house_style") != "mansion"]
    original["roads"] = [road for road in original["roads"] if "villa" not in road["id"] and "estate" not in road["id"]]
    original["map_size"]["height"] = 1000
    for person in original["people"]:
        person.pop("mansion_preferences_version")
        person["investment_preferences"].remove("mansion")
    preferences = {person["id"]: list(person["investment_preferences"]) for person in original["people"]}
    before = deepcopy(original)
    loaded = migrate_snapshot(original)
    assert original == before
    assert loaded["clock"] == original["clock"]
    for old, person in zip(original["people"], loaded["people"], strict=True):
        assert person["position"] == old["position"]
        assert person["money_cents"] == old["money_cents"]
        assert [goal for goal in person["investment_preferences"] if goal != "mansion"] == preferences[person["id"]]
        assert person["investment_preferences"].count("mansion") == 1
    assert len([place for place in loaded["places"] if place.get("house_style") == "mansion"]) == 2
    assert migrate_snapshot(loaded) == loaded


def test_saving_goal_buys_a_villa_when_funded_without_teleporting_the_household():
    world = build_fixture(7341)
    buyer, home = resident(world, "lea"), villa(world)
    buyer["investment_preferences"] = ["mansion", "savings"]
    roommate = resident(world, "tom")
    roommate["investment_preferences"] = ["mansion", "savings"]
    refresh_aspiration(world, roommate)
    assert roommate["investment_goal"] == "mansion"
    refresh_aspiration(world, buyer)
    assert buyer["investment_goal"] == "mansion"
    assert buyer["investment_target_cents"] == MANSION_PRICE
    before = deepcopy(world)
    assert not buy_house(world, buyer, home, datetime.fromisoformat(world["clock"]))
    assert world == before
    buyer["money_cents"] = MANSION_PRICE + CASH_RESERVE
    positions = {person["id"]: dict(person["position"]) for person in world["people"]}
    cars = deepcopy(world["vehicles"])
    treasury = world["economy"]["treasury_cents"]
    consider_prosperity(world, datetime.fromisoformat("2031-05-12T09:00:00"))
    assert buyer["home_place_id"] == home["id"]
    assert resident(world, "tom")["home_place_id"] == home["id"]
    assert home["owner_household_id"] == buyer["household_id"]
    assert not home.get("sale_price_cents")
    assert len(home["driveway"]["parking_positions"]) == 2
    assert world["vehicles"] == cars
    assert {person["id"]: person["position"] for person in world["people"]} == positions
    assert buyer["money_cents"] == CASH_RESERVE
    assert world["economy"]["treasury_cents"] == treasury + MANSION_PRICE
    assert buyer["investment_goal"] != "mansion"
    assert roommate["investment_goal"] != "mansion"
    assert not buy_house(world, resident(world, "elena"), home, datetime.fromisoformat(world["clock"]))
    assert migrate_snapshot(world)["places"] == world["places"]


def test_two_household_cars_use_separate_bays_and_reserve_incoming_parking():
    world = build_fixture(7341)
    home = villa(world)
    alice, oliver, emma = [resident(world, slug) for slug in ("alice", "oliver", "emma")]
    alice["money_cents"] = MANSION_PRICE + CASH_RESERVE
    now = datetime.fromisoformat(world["clock"])
    assert buy_house(world, alice, home, now)
    workshop = next(place for place in world["places"] if place["id"] == "place:workshop")
    for person in (alice, oliver):
        person["money_cents"] = 200_000
        person["position"] = _position_at(person, workshop)
        person["target_place_id"] = workshop["id"]
        assert buy_car(world, person, home, now)
        trip = _car_journey(world, person, home)
        assert trip is not None
        person["car_trip"] = trip
    assert alice["car_trip"]["parking_position"] != oliver["car_trip"]["parking_position"]
    assert not car_purchase_available(world, emma, "standard")
    assert not car_purchase_available(world, emma, "sports")
    assert home_parking_point(world, home, "vehicle:third") is None
    for person in (alice, oliver):
        car = next(vehicle for vehicle in world["vehicles"] if vehicle["owner_id"] == person["id"])
        car["position"] = person["car_trip"]["parking_position"]
        car["parking_place_id"] = home["id"]
        person.pop("car_trip")
    assert home_parking_point(world, home, "vehicle:third") is None


def test_mansion_walks_enter_and_leave_through_the_gate():
    world = build_fixture(7341)
    home, person = villa(world), resident(world, "lea")
    doorstep = _position_at(person, home)
    outside = {"x": 365, "y": 350}
    for start, end in [(outside, doorstep), (doorstep, outside)]:
        route = _residential_walk_route(world, start, end)
        assert route[0] == start and route[-1] == end
        assert any(a["x"] == b["x"] == home["estate_gate"]["x"]
                   and min(a["y"], b["y"]) <= home["estate_gate"]["y"] <= max(a["y"], b["y"])
                   for a, b in pairwise(route))
