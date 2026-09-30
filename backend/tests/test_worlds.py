import json
from datetime import datetime, timedelta
from itertools import pairwise
from math import ceil, hypot

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import create_app
from db import engine
from generation.fixture_town import build_fixture
from persistence.models import WorldSnapshot
from services.worlds import tick_running_worlds
from simulation.economy import (
    BAR_VISIT_CENTS,
    PRICE_PERCENT_OPTIONS,
    charge_daily_overhead,
    consider_takeovers,
    pay_owner_dividends,
    pay_work_seconds,
    price_cents,
    record_regional_sales,
    take_over_business,
)
from simulation.tick import (
    STATIONS,
    _car_journey,
    _grocery_browsing_minutes,
    _is_business_open_and_staffed,
    _next_service,
    _position_at,
    _service_state,
    _station_walk_minutes,
    _train_journey,
    _walking_minutes,
    advance,
    advance_seconds,
)
from simulation.versions import WORLD_FORMAT_VERSION, migrate_snapshot


def _start_at(person: dict, place: dict) -> None:
    person["position"] = _position_at(person, place)
    person["target_place_id"] = place["id"]
    person.pop("direct_walk", None)
    person.pop("route", None)


def _staff_at(world: dict, person_id: str) -> None:
    worker = next(person for person in world["people"] if person["id"] == person_id)
    workplace = next(place for place in world["places"] if place["id"] == worker["workplace_id"])
    _start_at(worker, workplace)
    worker["activity"] = f"Working as {worker['role'].lower()}"


def test_fixture_world_can_advance_and_reload():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 90111}).json()
        world_id = world["id"]
        expected_clock = (
            datetime.fromisoformat(world["clock"]) + timedelta(minutes=30)
        ).isoformat(timespec="seconds")
        advanced = client.post(f"/api/worlds/{world_id}/advance", json={"minutes": 30})
        assert advanced.status_code == 200
        reloaded = client.get(f"/api/worlds/{world_id}")
        assert reloaded.status_code == 200
        assert reloaded.json()["clock"] == expected_clock
        assert reloaded.json()["world_format_version"] == WORLD_FORMAT_VERSION
        assert reloaded.json()["revision"] == 1
        assert len(reloaded.json()["people"]) == 15
        index = client.get("/api/worlds")
        assert index.status_code == 200
        assert any(item["id"] == world_id for item in index.json())


def test_run_command_and_revisions_reject_stale_mutations():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 90112}).json()
        started = client.post(
            f"/api/worlds/{world['id']}/run",
            json={"running": True, "speed": 2, "expected_revision": world["revision"]},
        )
        assert started.status_code == 200
        assert started.json()["simulation"]["running"] is True
        assert started.json()["simulation"]["speed"] == 2

        stale = client.post(
            f"/api/worlds/{world['id']}/advance",
            json={"minutes": 1, "expected_revision": world["revision"]},
        )
        assert stale.status_code == 409


def test_server_tick_advances_running_world_at_selected_speed():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 90113}).json()
        started = client.post(
            f"/api/worlds/{world['id']}/run",
            json={"running": True, "speed": 2, "expected_revision": world["revision"]},
        ).json()

        tick_running_worlds()

        observed = client.get(f"/api/worlds/{world['id']}").json()
        assert observed["simulation"]["elapsed_seconds"] == 30
        assert observed["revision"] == started["revision"] + 1


def test_fixed_second_steps_match_one_grouped_advance():
    grouped = build_fixture(79)
    stepped = build_fixture(79)

    advance(grouped, 5)
    for _ in range(20):
        advance_seconds(stepped, 15)

    assert stepped["clock"] == grouped["clock"]
    assert stepped["simulation"]["elapsed_seconds"] == grouped["simulation"]["elapsed_seconds"]
    assert stepped["people"] == grouped["people"]


def test_legacy_snapshot_is_loaded_additively_until_a_command_saves_it():
    legacy = build_fixture(12)
    legacy.pop("world_format_version")
    legacy.pop("revision")

    with Session(engine) as session:
        session.add(
            WorldSnapshot(id=legacy["id"], seed=12, state_json=json.dumps(legacy))
        )
        session.commit()

    with TestClient(create_app()) as client:
        loaded = client.post("/api/worlds", json={"seed": 12}).json()

    assert "world_format_version" not in legacy
    assert loaded["world_format_version"] == WORLD_FORMAT_VERSION
    assert loaded["revision"] == 0
    with Session(engine) as session:
        stored = session.get(WorldSnapshot, legacy["id"])
        assert stored is not None
        assert "world_format_version" not in json.loads(stored.state_json)

    with TestClient(create_app()) as client:
        advanced = client.post(f"/api/worlds/{legacy['id']}/advance", json={"minutes": 1})

    assert advanced.status_code == 200
    with Session(engine) as session:
        stored = session.get(WorldSnapshot, legacy["id"])
        assert stored is not None
        assert stored.world_format_version == WORLD_FORMAT_VERSION
        assert json.loads(stored.state_json)["revision"] == 1


def test_render_state_and_inspector_are_available():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 222}).json()
        render = client.get(f"/api/worlds/{world['id']}/render-state")
        inspector = client.get(f"/api/worlds/{world['id']}/entities/person:elena")
        assert len(render.json()["entities"]) == 18
        assert inspector.json()["name"] == "Elena Rossi"


def test_backend_serves_the_built_frontend():
    with TestClient(create_app()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<div id=\"root\"></div>" in response.text


def test_commute_starts_from_the_residents_actual_position():
    world = build_fixture(77)
    marco = next(person for person in world["people"] if person["id"] == "person:marco")
    starting_position = dict(marco["position"])
    advanced = advance(world, 10)
    marco = next(person for person in advanced["people"] if person["id"] == "person:marco")
    assert marco["activity"].startswith("Walking to") or "Folk Loop" in marco["activity"]
    assert marco["position"] != starting_position
    assert len(marco["route"]) >= 2
    assert marco["route"][0] == starting_position
    assert marco["journey"]["legs"][0]["progress"] > 0


def test_late_worker_reaches_work_before_working_and_route_survives_reload():
    world = build_fixture(770)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    work = next(place for place in world["places"] if place["id"] == elena["workplace_id"])
    world["clock"] = "2031-05-12T08:05:00"
    elena["position"] = {"x": 500, "y": 350}
    elena["target_place_id"] = elena["home_place_id"]
    origin = dict(elena["position"])

    advance(world, 0)
    assert elena["activity"].startswith("Walking to")
    assert elena["position"] == origin
    route = elena["route"]
    assert route[0] == origin
    assert len(route) > 2
    assert elena["journey"]["legs"][0]["progress"] == 0

    restored = json.loads(json.dumps(world))
    rider = next(person for person in restored["people"] if person["id"] == "person:elena")
    advance(restored, 10)
    assert rider["activity"].startswith("Walking to")
    assert rider["route"] == route
    assert 0 < rider["journey"]["legs"][0]["progress"] < 1

    advance(restored, 50)
    assert rider["activity"] == "Working as baker"
    assert rider["target_place_id"] == work["id"]
    assert "direct_walk" not in rider


def test_train_uses_stable_seats_and_alights_at_the_backend_stop():
    world = build_fixture(78)
    station = {"id": "station:market", "position": {"x": 510, "y": 58}}
    for person in world["people"]:
        if person["id"] in {"person:marco", "person:tom", "person:ana", "person:sofia", "person:lucas"}:
            _start_at(person, station)

    advance(world, 4)

    riders = [person for person in world["people"] if person.get("on_train")]
    state = world["trains"][0]["state"]
    assert state["at_station"] is None
    assert 1 <= len(riders) <= state["capacity"]
    assert {(rider["train_car_index"], rider["train_seat_index"]) for rider in riders} == {
        (seat // state["car_capacity"], seat % state["car_capacity"])
        for seat in range(len(riders))
    }
    assert state["carriages"][0]["passenger_ids"] == [
        rider["id"] for rider in riders if rider["train_car_index"] == 0
    ]

    advance(world, 9)

    assert world["trains"][0]["state"]["at_station"] == "station:eastgate"
    assert world["trains"][0]["state"]["service_state"] == "stopped"
    advance_seconds(world, 15)
    assert not any(
        person.get("on_train") and person.get("train_arrival_id") == "station:eastgate"
        for person in world["people"]
    )


def test_train_egress_uses_the_same_pedestrian_speed_as_other_walks():
    world = build_fixture(78)
    marco = next(person for person in world["people"] if person["id"] == "person:marco")
    home = next(place for place in world["places"] if place["id"] == marco["home_place_id"])
    work = next(place for place in world["places"] if place["id"] == marco["workplace_id"])
    journey = _train_journey(home, work, datetime.fromisoformat("2031-05-12T07:00:00"))

    assert journey is not None
    assert _station_walk_minutes(journey["arrival"], work) == journey["egress_minutes"]
    arrival = journey["arrival"]["position"]
    destination = work["position"]
    assert journey["egress_minutes"] == ceil(
        hypot(destination["x"] - arrival["x"], destination["y"] - arrival["y"]) / 18
    )


def test_ten_person_platform_fills_eight_seats_then_recovers_on_next_service():
    world = build_fixture(781)
    empty = build_fixture(782)
    station = STATIONS["market"]
    world["places"].append({
        "id": "place:far-east-work", "name": "Far East Work",
        "kind": "workplace", "position": {"x": 1200, "y": 500},
    })
    crowd = world["people"][:10]
    for person in crowd:
        _start_at(person, station)
        person["train_trip"] = {
            "departure_id": station["id"],
            "arrival_id": STATIONS["eastgate"]["id"],
            "destination_id": (
                "place:far-east-work" if person["id"] in {"person:sofia", "person:tom"}
                else person["workplace_id"]
            ),
            "phase": "access",
        }

    advance(world, 0)
    queue = next(item for item in world["station_queues"] if item["station_id"] == station["id"])
    assert len(queue["entries"]) == 10
    assert [entry["person_id"] for entry in queue["entries"]] == sorted(person["id"] for person in crowd)

    advance(world, 3)
    advance(empty, 3)
    assert world["trains"][0]["state"]["distance"] == empty["trains"][0]["state"]["distance"]
    assert len(world["trains"][0]["state"]["passenger_ids"]) == 8
    assert len(queue["entries"]) == 2
    assert all(
        "next scheduled departure is 08:18" in person["explanation"]
        for person in crowd if person["id"] in {"person:sofia", "person:tom"}
    )
    seats = {(person["train_car_id"], person["train_seat_id"]) for person in crowd if person.get("on_train")}
    assert len(seats) == 8
    assert all(len(carriage["seats"]) == 4 for carriage in world["trains"][0]["state"]["carriages"])

    restored = json.loads(json.dumps(world))
    restored_queue = next(item for item in restored["station_queues"] if item["station_id"] == station["id"])
    assert len(restored_queue["entries"]) == 2
    assert {(person["train_car_id"], person["train_seat_id"]) for person in restored["people"] if person.get("on_train")} == seats
    advance(restored, 10)
    advance_seconds(restored, 15)
    assert not any(person.get("on_train") and person.get("train_arrival_id") == STATIONS["eastgate"]["id"] for person in restored["people"])
    assert len(restored_queue["entries"]) == 2

    advance(restored, 35)
    assert len(restored_queue["entries"]) == 0
    assert sum(bool(person.get("on_train")) for person in restored["people"]) == 2


def test_a_missed_train_causes_a_faster_walk_from_the_actual_platform():
    world = build_fixture(786)
    station = STATIONS["market"]
    for person in world["people"][:10]:
        _start_at(person, station)
        person["train_trip"] = {
            "departure_id": station["id"],
            "arrival_id": STATIONS["eastgate"]["id"],
            "destination_id": person["workplace_id"],
            "phase": "access",
        }

    advance(world, 3)
    queue = next(item for item in world["station_queues"] if item["station_id"] == station["id"])
    assert queue["entries"] == []
    walkers = [
        person for person in world["people"][:10]
        if person.get("direct_walk") and not person.get("train_trip")
    ]
    assert len(walkers) == 2
    assert all(person["direct_walk"]["route"][0] == _position_at(person, station) for person in walkers)
    assert all(not person.get("train_trip") for person in walkers)


def test_alighting_frees_seats_before_fifo_boarding_at_the_same_station():
    world = build_fixture(784)
    eastgate = STATIONS["eastgate"]
    for index, person in enumerate(world["people"][:11]):
        if index < 8:
            person["train_trip"] = {
                "departure_id": STATIONS["market"]["id"],
                "arrival_id": eastgate["id"],
                "destination_id": person["workplace_id"],
                "phase": "aboard",
                "boarded_departure_at": "2031-05-12T07:33:00",
            }
            person["on_train"] = True
            person["train_car_index"], person["train_seat_index"] = divmod(index, 4)
            person["train_arrival_id"] = eastgate["id"]
        else:
            _start_at(person, eastgate)
            person["train_trip"] = {
                "departure_id": eastgate["id"],
                "arrival_id": STATIONS["rowan"]["id"],
                "destination_id": person["workplace_id"],
                "phase": "access",
            }
    world["clock"] = "2031-05-12T07:42:45"
    advance(world, 0)
    queue = next(item for item in world["station_queues"] if item["station_id"] == eastgate["id"])
    first_waiting = queue["entries"][0]["person_id"]
    advance_seconds(world, 15)
    assert sum(bool(person.get("on_train")) for person in world["people"]) == 8
    advance_seconds(world, 15)
    assert sum(bool(person.get("on_train")) for person in world["people"]) == 1
    boarded = next(person for person in world["people"] if person.get("on_train"))
    assert boarded["id"] == first_waiting
    assert (boarded["train_car_index"], boarded["train_seat_index"]) == (0, 0)


def test_overnight_layover_closes_doors_and_resumes_at_six():
    world = build_fixture(783)
    world["clock"] = "2031-05-12T23:59:45"
    station = STATIONS["market"]
    rider = world["people"][0]
    _start_at(rider, station)
    rider["train_trip"] = {
        "departure_id": station["id"],
        "arrival_id": STATIONS["eastgate"]["id"],
        "destination_id": rider["workplace_id"],
        "phase": "access",
    }
    advance(world, 0)
    rider["train_trip"]["missed_service_at"] = "2031-05-12T23:17:45"
    advance_seconds(world, 15)
    state = world["trains"][0]["state"]
    assert state["service_state"] == "parked"
    assert state["at_station"] == station["id"]
    assert state["doors_open"] is False
    assert not rider.get("on_train")
    assert "parked from midnight to 06:00" in rider["explanation"]
    assert rider.get("train_trip") is None
    assert state["stations"][0]["next_departure_at"] == "2031-05-13T06:03:00"

    advance(world, 5 * 60 + 59)
    assert world["trains"][0]["state"]["service_state"] == "parked"
    assert world["trains"][0]["state"]["distance"] == state["distance"]
    _start_at(rider, station)
    rider["train_trip"] = {
        "departure_id": station["id"],
        "arrival_id": STATIONS["eastgate"]["id"],
        "destination_id": rider["workplace_id"],
        "phase": "access",
    }
    advance(world, 0)
    assert "parked overnight until 06:00" in rider["explanation"]
    advance(world, 1)
    assert world["trains"][0]["state"]["service_state"] == "stopped"
    advance_seconds(world, 15)
    assert rider["on_train"] is True
    assert world["trains"][0]["state"]["doors_open"] is True


def test_timetable_never_promises_an_overnight_departure():
    market, eastgate = STATIONS["market"], STATIONS["eastgate"]
    departure, arrival = _next_service(
        market, eastgate, datetime.fromisoformat("2031-05-12T23:45:00")
    )
    assert departure.isoformat(timespec="minutes") == "2031-05-13T06:03"
    assert arrival.isoformat(timespec="minutes") == "2031-05-13T06:13"
    assert _service_state(0)["service_state"] == "parked"
    assert _service_state(6 * 60)["service_state"] == "stopped"
    world = build_fixture(785)
    worker = next(person for person in world["people"] if person["id"] == "person:marco")
    workplace = next(place for place in world["places"] if place["id"] == worker["workplace_id"])
    origin = {"position": market["position"]}
    assert _train_journey(origin, workplace, datetime.fromisoformat("2031-05-12T23:50:00")) is None
    morning = _train_journey(origin, workplace, datetime.fromisoformat("2031-05-13T05:50:00"))
    assert morning is not None
    assert morning["departure_at"] == "2031-05-13T06:03:00"


def test_distant_commuters_walk_to_owned_cars_drive_roads_and_park_before_work():
    world = build_fixture(787)
    lea = next(person for person in world["people"] if person["id"] == "person:lea")
    lucas = next(person for person in world["people"] if person["id"] == "person:lucas")
    near = next(place for place in world["places"] if place["id"] == "place:rowan-2")
    assert _car_journey(world, lea, near) is None

    advance(world, 0)
    assert lea["car_trip"]["phase"] == "access"
    assert lucas["car_trip"]["phase"] == "access"
    assert next(vehicle for vehicle in world["vehicles"] if vehicle["id"] == "vehicle:lea")["reserved_by"] == lea["id"]
    work = next(place for place in world["places"] if place["id"] == lea["workplace_id"])
    assert _car_journey(world, lea, work) is None

    advance(world, 8)
    car = next(vehicle for vehicle in world["vehicles"] if vehicle["id"] == "vehicle:lea")
    assert car["state"] == "driving"
    assert car["driver_id"] == lea["id"]
    assert car["heading"] == 90
    assert lea["in_vehicle_id"] == car["id"]
    assert lea["position"] == car["position"]
    assert lea["journey"]["legs"][0]["edge_ids"] == [
        "road:rowan-north", "road:west-avenue", "road:orchard-street"
    ]
    route = lea["car_trip"]["road_route"]
    assert all(
        left["x"] == right["x"] or left["y"] == right["y"]
        for left, right in pairwise(route[1:-1])
    )

    restored = json.loads(json.dumps(world))
    advance(world, 12)
    advance(restored, 12)
    assert restored["vehicles"] == world["vehicles"]
    assert restored["people"] == world["people"]
    assert car["state"] == "parked"
    assert car.get("driver_id") is None
    assert car.get("reserved_by") is None
    assert lea.get("car_trip") is None
    assert lea["target_place_id"] == work["id"]


def test_owner_can_drive_the_parked_car_home_after_work():
    world = build_fixture(788)
    advance(world, 17 * 60 - 7 * 60 - 30)
    lea = next(person for person in world["people"] if person["id"] == "person:lea")
    car = next(vehicle for vehicle in world["vehicles"] if vehicle["id"] == "vehicle:lea")
    assert lea["car_trip"]["destination_id"] == lea["home_place_id"]
    assert car["reserved_by"] == lea["id"]
    advance(world, 40)
    assert car["state"] == "parked"
    assert car["parking_place_id"] == lea["home_place_id"]
    assert lea.get("in_vehicle_id") is None
    assert lea.get("car_trip") is None
    advance(world, 50)
    lucas = next(person for person in world["people"] if person["id"] == "person:lucas")
    van = next(vehicle for vehicle in world["vehicles"] if vehicle["id"] == "vehicle:lucas")
    assert van["parking_place_id"] == lucas["home_place_id"]
    assert van["state"] == "parked"


def test_driving_state_survives_the_saved_world_api_round_trip():
    with TestClient(create_app()) as client:
        created = client.post("/api/worlds", json={"seed": 789}).json()
        advanced = client.post(
            f"/api/worlds/{created['id']}/advance", json={"minutes": 8}
        ).json()
        saved = client.get(f"/api/worlds/{created['id']}").json()
        assert saved["vehicles"] == advanced["vehicles"]
        lea = next(person for person in saved["people"] if person["id"] == "person:lea")
        car = next(vehicle for vehicle in saved["vehicles"] if vehicle["id"] == "vehicle:lea")
        assert lea["car_trip"]["phase"] == "driving"
        assert lea["in_vehicle_id"] == car["id"]
        assert car["driver_id"] == lea["id"]
        assert car["position"] == lea["position"]


def test_household_members_take_turns_grocery_shopping_and_shoppers_move_in_market():
    world = build_fixture(45)
    shopper = next(person for person in world["people"] if person["id"] == "person:elena")
    next_shopper = next(person for person in world["people"] if person["id"] == "person:marco")
    household = next(
        household for household in world["households"] if household["id"] == shopper["household_id"]
    )
    household["food_servings"] = 2
    market = next(place for place in world["places"] if place["id"] == "place:supermarket")
    workplace = next(place for place in world["places"] if place["id"] == shopper["workplace_id"])
    _start_at(shopper, workplace)
    worker = next(person for person in world["people"] if person["id"] == "person:diego")
    _start_at(worker, market)
    world["clock"] = "2031-05-12T16:59:00"

    advance(world, 45)

    assert shopper["activity"] == "Shopping at Hearth Market"
    assert household["food_servings"] == 6
    assert household["grocery_servings_to_buy"] == 4
    assert shopper["carrying_groceries"] is True
    first_position = dict(shopper["position"])
    advance(world, 2)
    assert shopper["position"] != first_position
    assert next_shopper["activity"] != "Shopping at Hearth Market"
    advance(world, 100)
    assert shopper.get("carrying_groceries") is None

    household["food_servings"] = 2
    next_workplace = next(
        place for place in world["places"] if place["id"] == next_shopper["workplace_id"]
    )
    _start_at(next_shopper, next_workplace)
    _start_at(worker, market)
    world["clock"] = "2031-05-13T16:59:00"
    advance(world, 70)
    assert next_shopper["activity"] == "Shopping at Hearth Market"


def test_grocery_browsing_time_scales_with_household_servings():
    single = {"member_ids": ["person:one"], "grocery_servings_to_buy": 3}
    family_of_four = {
        "member_ids": ["person:one", "person:two", "person:three", "person:four"],
        "grocery_servings_to_buy": 12,
    }

    assert _grocery_browsing_minutes(family_of_four) > _grocery_browsing_minutes(single)


def test_groceries_are_acquired_only_after_the_shopper_arrives():
    world = build_fixture(451)
    shopper = next(person for person in world["people"] if person["id"] == "person:elena")
    household = next(item for item in world["households"] if item["id"] == shopper["household_id"])
    household["food_servings"] = 2
    _staff_at(world, "person:diego")
    world["clock"] = "2031-05-12T17:00:00"
    origin = dict(shopper["position"])

    advance(world, 0)
    assert shopper["evening_plan"]["phase"] == "travel"
    assert shopper["route"][0] == origin
    advance(world, 30)
    assert shopper["activity"] == "Walking to Hearth Market"
    assert household["food_servings"] == 2

    advance(world, 25)
    assert shopper["activity"] == "Shopping at Hearth Market"
    assert household["food_servings"] == 6


def test_gardener_works_away_from_home_and_wages_are_shared():
    world = build_fixture(450)
    bruno = next(person for person in world["people"] if person["id"] == "person:bruno")
    workplace = next(place for place in world["places"] if place["id"] == "place:florist")
    household = next(item for item in world["households"] if item["id"] == bruno["household_id"])
    assert bruno["workplace_id"] == workplace["id"] != bruno["home_place_id"]
    _start_at(bruno, workplace)
    world["pets"][0]["last_walk_at"] = "2031-05-12T07:30:00"
    world["clock"] = "2031-05-12T08:00:00"
    personal_before, shared_before = bruno["money_cents"], household["money_cents"]

    advance(world, 15)

    assert bruno["activity"] == "Working as gardener"
    assert bruno["money_cents"] == personal_before + 150
    assert household["money_cents"] == shared_before + 150
    assert [entry["amount_cents"] for entry in world["economy"]["ledger"] if entry["to"] in {bruno["id"], household["id"]}] == [150, 150]


def test_old_gardener_assignment_and_missing_accounts_upgrade_in_memory():
    saved = build_fixture(453)
    bruno = next(person for person in saved["people"] if person["id"] == "person:bruno")
    bruno["workplace_id"] = bruno["home_place_id"]
    bruno["activity"] = "Working as gardener"
    saved.pop("economy")
    for person in saved["people"]:
        person.pop("money_cents")
    for household in saved["households"]:
        household.pop("money_cents")
    for place in saved["places"]:
        place.pop("business", None)

    loaded = migrate_snapshot(saved)

    upgraded_bruno = next(person for person in loaded["people"] if person["id"] == "person:bruno")
    assert upgraded_bruno["workplace_id"] == "place:florist"
    assert upgraded_bruno["activity"] == "Tending the garden"
    assert loaded["economy"]["household_contribution_percent"] == 50
    assert bruno["workplace_id"] == bruno["home_place_id"]


def test_household_contribution_is_saved_and_validated():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 454}).json()
        response = client.put(
            f"/api/worlds/{world['id']}/economy/household-contribution", json={"percent": 75}
        )
        assert response.status_code == 200
        assert response.json()["economy"]["household_contribution_percent"] == 75
        assert client.get(f"/api/worlds/{world['id']}").json()["economy"]["household_contribution_percent"] == 75
        assert client.put(
            f"/api/worlds/{world['id']}/economy/household-contribution", json={"percent": 101}
        ).status_code == 422


def test_groceries_and_bar_visits_transfer_money_once():
    world = build_fixture(451)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    household = next(item for item in world["households"] if item["id"] == elena["household_id"])
    market = next(place for place in world["places"] if place["id"] == "place:supermarket")
    market["business"]["price_percent"] = 120
    household["food_servings"] = 2
    _start_at(elena, market)
    _staff_at(world, "person:diego")
    world["clock"] = "2031-05-12T17:00:00"
    shared_before, market_before = household["money_cents"], market["business"]["balance_cents"]

    advance(world, 0)
    price = household["grocery_servings_to_buy"] * price_cents(market)
    assert household["money_cents"] == shared_before - price
    assert market["business"]["balance_cents"] == market_before + price - household["grocery_servings_to_buy"] * 75
    assert household["food_servings"] == 6
    advance(world, 0)
    assert household["money_cents"] == shared_before - price

    bar = next(place for place in world["places"] if place["id"] == "place:lantern-bar")
    _staff_at(world, "person:marta")
    _start_at(elena, bar)
    elena.pop("evening_plan", None)
    elena["needs"].update({"hunger": 0, "rest": 0, "social": 100, "boredom": 0})
    world["clock"] = "2031-05-12T18:00:00"
    personal_before, bar_before = elena["money_cents"], bar["business"]["balance_cents"]
    advance(world, 0)
    assert elena["money_cents"] == personal_before - BAR_VISIT_CENTS
    assert bar["business"]["balance_cents"] == bar_before + BAR_VISIT_CENTS - 360
    advance(world, 0)
    assert elena["money_cents"] == personal_before - BAR_VISIT_CENTS


def test_household_cannot_receive_unpaid_groceries():
    world = build_fixture(455)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    household = next(item for item in world["households"] if item["id"] == elena["household_id"])
    market = next(place for place in world["places"] if place["id"] == "place:supermarket")
    household["food_servings"] = 2
    household["money_cents"] = 0
    _start_at(elena, market)
    _staff_at(world, "person:diego")
    world["clock"] = "2031-05-12T17:00:00"

    advance(world, 0)

    assert household["food_servings"] == 2
    assert not any(entry["reason"] == "grocery" for entry in world["economy"]["ledger"])


def test_empty_business_closes_when_it_cannot_pay_operating_costs():
    world = build_fixture(452)
    bar = next(place for place in world["places"] if place["id"] == "place:lantern-bar")
    bar["business"]["balance_cents"] = 1_999
    world["clock"] = "2031-05-12T23:59:45"

    advance_seconds(world, 15)

    assert bar["business"]["status"] == "bankrupt"
    assert bar["business"]["balance_cents"] == 1_999
    assert any("The Lantern Bar closed" in event["summary"] for event in world["events"])


def test_regional_customers_pay_a_staffed_business_and_respond_to_price():
    from datetime import datetime

    normal = build_fixture(456)
    expensive = build_fixture(456)
    for world, percent in ((normal, 100), (expensive, 130)):
        bakery = next(place for place in world["places"] if place["id"] == "place:bakery")
        bakery["business"]["price_percent"] = percent
        _staff_at(world, "person:elena")
        record_regional_sales(world, datetime.fromisoformat("2031-05-12T10:00:00"), _is_business_open_and_staffed)
        first_balance = bakery["business"]["balance_cents"]
        record_regional_sales(world, datetime.fromisoformat("2031-05-12T10:00:00"), _is_business_open_and_staffed)
        assert bakery["business"]["balance_cents"] == first_balance
    normal_bakery = next(place for place in normal["places"] if place["id"] == "place:bakery")
    expensive_bakery = next(place for place in expensive["places"] if place["id"] == "place:bakery")
    assert normal_bakery["business"]["regional_visits_today"] > expensive_bakery["business"]["regional_visits_today"]
    assert normal_bakery["business"]["balance_cents"] > 100_000
    assert any(entry["reason"] == "Regional customers" for entry in normal["economy"]["ledger"])


def test_takeover_settles_debt_adds_capital_and_reopens_without_moving_resident():
    from datetime import datetime

    world = build_fixture(457)
    bakery = next(place for place in world["places"] if place["id"] == "place:bakery")
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    bakery["business"].update({"status": "bankrupt", "balance_cents": 0,
        "debts": [{"to": "outside", "amount_cents": 2_000, "reason": "Unpaid rent"}], "debt_cents": 2_000})
    elena["money_cents"] = 12_000
    position = dict(elena["position"])

    take_over_business(world, bakery["id"], elena["id"], 110, datetime.fromisoformat(world["clock"]))

    assert elena["money_cents"] == 2_000
    assert elena["position"] == position
    assert bakery["business"]["balance_cents"] == 8_000
    assert bakery["business"]["owner_id"] == elena["id"]
    assert bakery["business"]["status"] == "open"
    assert bakery["business"]["debt_cents"] == 0
    assert price_cents(bakery) == 660
    assert any("Elena Rossi took over Rosa Bakery" in event["summary"] for event in world["events"])


def test_resident_can_autonomously_take_over_viable_failed_workplace():
    from datetime import datetime

    world = build_fixture(458)
    bakery = next(place for place in world["places"] if place["id"] == "place:bakery")
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    bakery["business"].update({"status": "bankrupt", "balance_cents": 0,
        "debts": [{"to": "outside", "amount_cents": 300, "reason": "Unpaid bill"}], "debt_cents": 300})
    elena["money_cents"] = 12_000

    consider_takeovers(world, datetime.fromisoformat("2031-05-13T09:00:00"))

    assert bakery["business"]["owner_id"] == elena["id"]
    assert bakery["business"]["price_percent"] in PRICE_PERCENT_OPTIONS
    assert bakery["business"]["status"] == "open"


def test_staffed_bakery_covers_a_day_of_wages_supplies_and_overhead():
    from datetime import datetime

    world = build_fixture(461)
    bakery = next(place for place in world["places"] if place["id"] == "place:bakery")
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    _staff_at(world, elena["id"])
    initial_balance = bakery["business"]["balance_cents"]
    for hour in range(9, 17):
        now = datetime.fromisoformat(f"2031-05-12T{hour:02d}:00:00")
        record_regional_sales(world, now, _is_business_open_and_staffed)
        for _ in range(4):
            pay_work_seconds(world, elena, 15 * 60, now)
    charge_daily_overhead(world, datetime.fromisoformat("2031-05-13T00:00:00"))

    assert bakery["business"]["status"] == "open"
    assert bakery["business"]["balance_cents"] > initial_balance


def test_owner_dividend_keeps_two_days_of_expenses_in_the_business():
    from datetime import datetime

    world = build_fixture(462)
    bakery = next(place for place in world["places"] if place["id"] == "place:bakery")
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    bakery["business"]["owner_id"] = elena["id"]
    balance_before, money_before = bakery["business"]["balance_cents"], elena["money_cents"]

    pay_owner_dividends(world, datetime.fromisoformat("2031-05-12T00:00:00"))

    assert elena["money_cents"] > money_before
    assert bakery["business"]["balance_cents"] + elena["money_cents"] == balance_before + money_before
    assert bakery["business"]["balance_cents"] >= 2 * (9 * 60 * 20 + 2_000)


def test_legacy_bankruptcy_recovers_an_unpaid_bill_without_changing_the_saved_state():
    saved = build_fixture(459)
    bakery = next(place for place in saved["places"] if place["id"] == "place:bakery")
    bakery["business"] = {"status": "bankrupt", "balance_cents": 0}
    saved["events"].append({"at": "2031-05-12T14:10", "summary": "Rosa Bakery closed after it could no longer pay its workers."})

    loaded = migrate_snapshot(saved)
    upgraded = next(place for place in loaded["places"] if place["id"] == "place:bakery")

    assert upgraded["business"]["debt_cents"] == 300
    assert upgraded["business"]["price_percent"] == 100
    assert "debts" not in bakery["business"]


def test_takeover_and_pricing_api_persist_and_validate_balances():
    with TestClient(create_app()) as client:
        world = client.post("/api/worlds", json={"seed": 460}).json()
        bakery_id = "place:bakery"
        world_id = world["id"]
        # The isolated API world has a solvent bakery, so a takeover is refused.
        assert client.post(f"/api/worlds/{world_id}/businesses/{bakery_id}/takeover",
            json={"buyer_id": "person:elena", "price_percent": 110}).status_code == 409
        assert client.put(f"/api/worlds/{world_id}/businesses/{bakery_id}/price",
            json={"price_percent": 110}).status_code == 409
        assert client.put(f"/api/worlds/{world_id}/businesses/{bakery_id}/price",
            json={"price_percent": 145}).status_code == 422
        with Session(engine) as session:
            snapshot = session.get(WorldSnapshot, world_id)
            assert snapshot is not None
            state = json.loads(snapshot.state_json)
            bakery = next(place for place in state["places"] if place["id"] == bakery_id)
            bakery["business"].update({"status": "bankrupt", "balance_cents": 0,
                "debts": [{"to": "outside", "amount_cents": 300, "reason": "Unpaid bill"}], "debt_cents": 300})
            next(person for person in state["people"] if person["id"] == "person:elena")["money_cents"] = 12_000
            snapshot.state_json = json.dumps(state)
            session.add(snapshot)
            session.commit()
        acquired = client.post(f"/api/worlds/{world_id}/businesses/{bakery_id}/takeover",
            json={"buyer_id": "person:elena", "price_percent": 110})
        assert acquired.status_code == 200
        assert next(place for place in acquired.json()["places"] if place["id"] == bakery_id)["business"]["owner_id"] == "person:elena"
        repriced = client.put(f"/api/worlds/{world_id}/businesses/{bakery_id}/price",
            json={"price_percent": 120})
        assert repriced.status_code == 200
        assert next(place for place in client.get(f"/api/worlds/{world_id}").json()["places"] if place["id"] == bakery_id)["business"]["unit_price_cents"] == 720


def test_quiet_shop_worker_visits_bar_when_socially_inclined():
    world = build_fixture(46)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    bakery = next(place for place in world["places"] if place["id"] == elena["workplace_id"])
    bar = next(place for place in world["places"] if place["id"] == "place:lantern-bar")
    household = next(
        household for household in world["households"] if household["id"] == elena["household_id"]
    )
    household["food_servings"] = 6
    elena["needs"]["boredom"] = 40
    elena["social_inclination"] = 0.8
    _start_at(elena, bakery)
    world["clock"] = "2031-05-12T08:14:00"

    advance(world, 1)
    assert elena["needs"]["boredom"] == 42

    world["clock"] = "2031-05-12T16:59:00"
    _staff_at(world, "person:marta")
    advance(world, _walking_minutes(bakery, bar) + 8)

    assert elena["activity"] == "Socializing at The Lantern Bar"
    first_position = dict(elena["position"])
    advance(world, 3)
    assert elena["position"] != first_position


def test_evening_staff_cover_bar_and_cinema_shifts():
    world = build_fixture(47)
    marta = next(person for person in world["people"] if person["id"] == "person:marta")
    hugo = next(person for person in world["people"] if person["id"] == "person:hugo")
    _start_at(marta, next(place for place in world["places"] if place["id"] == marta["workplace_id"]))
    _start_at(hugo, next(place for place in world["places"] if place["id"] == hugo["workplace_id"]))
    world["clock"] = "2031-05-12T16:00:00"

    advance(world, 1)

    assert marta["activity"] == "Working as bartender"
    assert hugo["activity"] == "Working as projectionist"


def test_cinema_competes_with_bar_for_an_evening_choice():
    world = build_fixture(48)
    lea = next(person for person in world["people"] if person["id"] == "person:lea")
    household = next(
        household for household in world["households"] if household["id"] == lea["household_id"]
    )
    household["food_servings"] = 6
    lea["needs"]["boredom"] = 50
    lea["social_inclination"] = 0.2
    lea["cinema_inclination"] = 0.9
    workplace = next(place for place in world["places"] if place["id"] == lea["workplace_id"])
    cinema = next(place for place in world["places"] if place["id"] == "place:cinema")
    _start_at(lea, workplace)
    world["clock"] = "2031-05-12T16:59:00"
    _staff_at(world, "person:hugo")

    advance(world, _walking_minutes(workplace, cinema) + 6)

    assert lea["activity"] == "Watching a film at Clover Cinema"


def test_household_owner_walks_pippin_before_the_twelve_hour_limit():
    world = build_fixture(49)
    pippin = world["pets"][0]
    nora = next(person for person in world["people"] if person["id"] == "person:nora")
    bruno = next(person for person in world["people"] if person["id"] == "person:bruno")
    starting_position = dict(nora["position"])

    advance(world, 0)

    assert pippin["walk_status"] == "out for a walk"
    assert nora["activity"] == "Walking Pippin"
    assert bruno["activity"] != "Walking Pippin"

    advance(world, 1)
    assert nora["position"] != starting_position
    assert nora["route"]

    advance(world, 80)

    assert pippin["walk_status"] == "comfortable"
    assert pippin["needs"]["walk_out"] < 10


def test_missed_pet_walk_requires_cleanup_then_another_owner_walks_pippin():
    world = build_fixture(50)
    pippin = world["pets"][0]
    nora = next(person for person in world["people"] if person["id"] == "person:nora")
    bruno = next(person for person in world["people"] if person["id"] == "person:bruno")
    pippin["last_walk_at"] = "2031-05-11T18:00:00"

    advance(world, 0)

    assert pippin["accident_at_home"] is True
    assert nora["activity"] == "Cleaning after Pippin"

    advance(world, 20)

    assert pippin.get("accident_at_home") is None
    assert pippin["walk_status"] == "out for a walk"
    assert bruno["activity"] == "Heading home to walk Pippin"
    assert bruno["route"][0] != bruno["route"][-1]
    advance(world, 120)

    assert pippin["walk_status"] == "comfortable"


def test_people_eat_when_hunger_is_high_then_choose_varied_home_activities():
    world = build_fixture(51)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    world["clock"] = "2031-05-12T18:30:00"
    elena["needs"]["hunger"] = 100

    advance(world, 0)

    assert elena["activity"] == "Cooking and eating at home"
    assert elena["needs"]["hunger"] < 100

    elena["needs"]["hunger"] = 20
    advance(world, 1)

    assert elena["activity"] in {
        "Reading at home",
        "Tending the garden",
        "Calling a friend",
        "Doing household chores",
        "Practising a hobby",
    }


def test_rest_social_and_boredom_needs_drive_evening_choices():
    world = build_fixture(52)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    household = next(
        household for household in world["households"] if household["id"] == elena["household_id"]
    )
    household["food_servings"] = 6
    world["clock"] = "2031-05-12T19:00:00"
    elena["needs"].update({"hunger": 20, "rest": 100, "social": 20, "boredom": 0})

    advance(world, 0)
    assert elena["activity"] == "Sleeping at home"
    assert elena["needs"]["rest"] < 100

    world["clock"] = "2031-05-13T17:30:00"
    _staff_at(world, "person:marta")
    elena["needs"].update({"hunger": 20, "rest": 20, "social": 100, "boredom": 0})
    advance(world, 0)

    assert elena["activity"] in {
        "Walking to The Lantern Bar",
        "Meet neighbours at The Lantern Bar",
        "Socializing at The Lantern Bar",
    }


def test_residents_keep_sleeping_at_3am_after_their_rest_need_recovers():
    world = build_fixture(520)
    world["clock"] = "2031-05-13T03:00:00"
    world["pets"][0]["last_walk_at"] = "2031-05-13T02:00:00"
    for person in world["people"]:
        person["needs"].update({"rest": 0, "hunger": 100})

    advance(world, 0)

    assert all(person["activity"] == "Sleeping at home" for person in world["people"])
    assert all(person["target_place_id"] == person["home_place_id"] for person in world["people"])


def test_bedtime_yields_to_a_scheduled_late_shift_then_ends_in_the_morning():
    world = build_fixture(521)
    marta = next(person for person in world["people"] if person["id"] == "person:marta")
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    elena["needs"]["rest"] = 0

    world["clock"] = "2031-05-12T22:30:00"
    advance(world, 0)
    assert marta["activity"] != "Sleeping at home"
    assert elena["activity"] == "Sleeping at home"

    world["clock"] = "2031-05-13T06:00:00"
    advance(world, 0)
    assert elena["activity"] == "At home"


def test_bedtime_routes_a_resident_home_from_an_evening_outing():
    world = build_fixture(522)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    bar = next(place for place in world["places"] if place["id"] == "place:lantern-bar")
    elena["position"] = dict(bar["position"])
    elena["target_place_id"] = bar["id"]
    elena["activity"] = "Socializing at The Lantern Bar"
    world["clock"] = "2031-05-12T22:30:00"
    starting_position = dict(elena["position"])

    advance(world, 0)

    assert elena["activity"] == "Walking home to sleep"
    assert elena["position"] == starting_position
    assert elena["target_place_id"] == elena["home_place_id"]


def test_social_outing_routes_from_home_instead_of_teleporting_to_the_bar():
    world = build_fixture(53)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    home = next(place for place in world["places"] if place["id"] == elena["home_place_id"])
    elena["position"] = {"x": home["position"]["x"], "y": home["position"]["y"] + 28}
    elena["needs"].update({"hunger": 20, "rest": 20, "social": 100, "boredom": 0})
    world["clock"] = "2031-05-12T18:10:00"
    _staff_at(world, "person:marta")
    starting_position = dict(elena["position"])

    advance(world, 0)

    assert elena["activity"] == "Walking to The Lantern Bar"
    assert elena["position"] == starting_position
    assert elena["route"]
    advance(world, 1)
    assert elena["position"] != starting_position


def test_meals_preempt_sleep_and_lunch_breaks_reduce_hunger():
    world = build_fixture(54)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    household = next(
        household for household in world["households"] if household["id"] == elena["household_id"]
    )
    household["food_servings"] = 2
    elena["needs"].update({"hunger": 100, "rest": 100})
    world["clock"] = "2031-05-12T18:10:00"

    advance(world, 0)

    assert elena["activity"] == "Cooking and eating at home"
    assert elena["target_place_id"] == elena["home_place_id"]

    elena["needs"].update({"hunger": 70, "rest": 20})
    work = next(place for place in world["places"] if place["id"] == elena["workplace_id"])
    _start_at(elena, work)
    world["clock"] = "2031-05-13T12:00:00"
    advance(world, 0)

    assert elena["activity"] == "Eating lunch at work"
    assert elena["needs"]["hunger"] < 70


def test_market_requires_an_open_shifted_staff_member():
    world = build_fixture(55)
    market = next(place for place in world["places"] if place["id"] == "place:supermarket")
    diego = next(person for person in world["people"] if person["id"] == "person:diego")

    diego["activity"] = "At home"
    assert not _is_business_open_and_staffed(world, market, 18 * 60)

    diego["activity"] = "Working as shopkeeper"
    assert _is_business_open_and_staffed(world, market, 18 * 60)
    assert not _is_business_open_and_staffed(world, market, 20 * 60)
