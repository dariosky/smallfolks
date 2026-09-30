from copy import deepcopy
from datetime import datetime, timedelta

from generation.fixture_town import build_fixture
from simulation.prosperity import (
    SPORTS_CAR_PRICE,
    SPORTS_PALETTES,
    buy_car,
    consider_prosperity,
    refresh_aspiration,
    workshop_parking,
)
from simulation.tick import _car_journey, _position_at, advance
from simulation.versions import migrate_snapshot


def person(world, slug="lea"):
    return next(p for p in world["people"] if p["id"] == f"person:{slug}")


def place(world, slug):
    return next(p for p in world["places"] if p["id"] == f"place:{slug}")


def at_workshop(world, buyer):
    buyer["position"] = _position_at(buyer, place(world, "workshop"))
    buyer["target_place_id"] = "place:workshop"
    for vehicle in world["vehicles"]:
        if vehicle["owner_id"] == buyer["id"]:
            vehicle["position"] = workshop_parking(world, vehicle["id"])
            vehicle["parking_place_id"] = "place:workshop"


def test_preferences_vary_and_survive_reload_without_flipping_each_day():
    world = build_fixture(7341)
    goals = {p["investment_goal"] for p in world["people"]}
    assert goals == {"home", "car", "sports_car", "shop", "mansion", "savings"}
    assert {p["id"]: p["investment_preferences"] for p in world["people"]} == {
        p["id"]: p["investment_preferences"] for p in build_fixture(7341)["people"]
    }
    before = {p["id"]: p["investment_preferences"] for p in world["people"]}
    migrated = migrate_snapshot(world)
    consider_prosperity(migrated, datetime.fromisoformat("2031-05-12T09:00:00"))
    assert {p["id"]: p["investment_preferences"] for p in migrated["people"]} == before
    assert {p["investment_goal"] for p in migrated["people"]} == goals
    legacy = deepcopy(world)
    for resident in legacy["people"]:
        resident.pop("investment_preferences")
        resident["aspiration"] = "Saving for a larger home and driveway."
    assert {p["investment_goal"] for p in migrate_snapshot(legacy)["people"]} == goals


def test_shop_goal_does_not_force_a_bigger_house_first():
    world = build_fixture(7341)
    buyer = person(world, "elena")
    buyer["investment_preferences"] = ["shop", "sports_car", "home", "car", "savings"]
    buyer["money_cents"] = 230_000
    consider_prosperity(world, datetime.fromisoformat("2031-05-12T09:00:00"))
    assert any(
        p.get("business", {}).get("owner_id") == buyer["id"] for p in world["places"]
    )
    assert place(world, "rowan-1").get("house_style") is None
    assert world["construction_projects"] == []


def test_sports_car_purchase_is_arrival_gated_and_financed_with_workshop_receipt():
    world = build_fixture(7341)
    buyer = person(world)
    buyer["money_cents"] = 180_000
    now = datetime.fromisoformat(world["clock"])
    buyer["income_history"] = {
        (now.date() - timedelta(days=d)).isoformat(): 10_000 for d in range(1, 5)
    }
    home = place(world, "rowan-2")
    before = deepcopy(world)
    assert not buy_car(world, buyer, home, now, "sports")
    assert world == before
    at_workshop(world, buyer)
    dealer = place(world, "workshop")["dealership"]
    cash_before = dealer["balance_cents"]
    assert buy_car(world, buyer, home, now, "sports")
    car = next(v for v in world["vehicles"] if v["owner_id"] == buyer["id"])
    assert car["model"] == "sports"
    assert car["palette"] in SPORTS_PALETTES
    assert car["speed_units_per_minute"] == 144
    assert car["parking_place_id"] == "place:workshop"
    assert len(world["vehicles"]) == 2
    assert buyer["money_cents"] == 20_000
    assert dealer["balance_cents"] == cash_before + SPORTS_CAR_PRICE * 15 // 100
    assert dealer["cars_sold"] == 1
    assert world["loans"][0]["purpose"] == "sports_car"
    assert not buy_car(world, buyer, home, now, "sports")
    loaded = migrate_snapshot(world)
    assert loaded["vehicles"] == world["vehicles"]
    assert loaded["loans"] == world["loans"]


def test_sports_car_takes_less_time_on_the_same_route():
    world = build_fixture(7341)
    buyer = person(world)
    at_workshop(world, buyer)
    home = place(world, "rowan-2")
    regular = _car_journey(world, buyer, home, transport_required=True)
    car = next(v for v in world["vehicles"] if v["owner_id"] == buyer["id"])
    car["speed_units_per_minute"] = 144
    sports = _car_journey(world, buyer, home, transport_required=True)
    assert sports["road_route"] == regular["road_route"]
    assert sports["drive_seconds"] < regular["drive_seconds"]


def test_persistent_workshop_trip_replaces_the_owned_car_and_drives_it_home():
    world = build_fixture(7341)
    buyer = person(world)
    buyer["investment_preferences"] = ["sports_car", "shop", "home", "car", "savings"]
    buyer["money_cents"] = 300_000
    world["clock"] = "2031-05-12T08:59:55"
    refresh_aspiration(world, buyer)
    car = next(v for v in world["vehicles"] if v["owner_id"] == buyer["id"])
    advance(world, 1)
    assert car.get("model") != "sports"
    assert buyer["vehicle_purchase"]["model"] == "sports"
    assert buyer["car_trip"]["destination_id"] == "place:workshop"
    loaded = migrate_snapshot(world)
    purchase_recorded = False
    for _ in range(45):
        advance(loaded, 1)
        purchase_recorded |= any(
            entry["reason"] == "Sports car purchase"
            for entry in loaded["economy"]["ledger"]
        )
    upgraded = next(v for v in loaded["vehicles"] if v["owner_id"] == buyer["id"])
    assert upgraded["model"] == "sports"
    assert "vehicle_purchase" not in person(loaded)
    assert place(loaded, "workshop")["dealership"]["cars_sold"] == 1
    assert len(loaded["vehicles"]) == 2
    assert purchase_recorded


def test_full_parking_or_busy_car_does_not_issue_a_loan_or_charge_a_buyer():
    world = build_fixture(7341)
    buyer = person(world)
    buyer["money_cents"] = 300_000
    at_workshop(world, buyer)
    car = next(v for v in world["vehicles"] if v["owner_id"] == buyer["id"])
    car["reserved_by"] = buyer["id"]
    before = deepcopy(world)
    assert not buy_car(
        world,
        buyer,
        place(world, "rowan-2"),
        datetime.fromisoformat(world["clock"]),
        "sports",
    )
    assert world == before


def test_full_workshop_parking_does_not_spend_money_or_issue_a_loan():
    world = build_fixture(7341)
    buyer = person(world)
    world["vehicles"] = [v for v in world["vehicles"] if v["owner_id"] != buyer["id"]]
    at_workshop(world, buyer)
    now = datetime.fromisoformat(world["clock"])
    buyer["money_cents"] = 180_000
    buyer["income_history"] = {
        (now.date() - timedelta(days=d)).isoformat(): 10_000 for d in range(1, 5)
    }
    for index in range(7):
        position = workshop_parking(world)
        assert position is not None
        world["vehicles"].append(
            {
                "id": f"vehicle:blocker-{index}",
                "owner_id": "person:lucas",
                "position": position,
                "state": "parked",
            }
        )
    assert workshop_parking(world) is None
    before = deepcopy(world)
    assert not buy_car(world, buyer, place(world, "rowan-2"), now, "sports")
    assert world == before
