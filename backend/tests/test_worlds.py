import json
from datetime import datetime, timedelta
from math import ceil, hypot

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import create_app
from db import engine
from generation.fixture_town import build_fixture
from persistence.models import WorldSnapshot
from services.worlds import tick_running_worlds
from simulation.tick import (
    _grocery_browsing_minutes,
    _is_business_open_and_staffed,
    _station_walk_minutes,
    _train_journey,
    _walking_minutes,
    advance,
    advance_seconds,
)
from simulation.versions import WORLD_FORMAT_VERSION


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


def test_commute_is_a_timed_walking_activity():
    world = build_fixture(77)
    marco = next(person for person in world["people"] if person["id"] == "person:marco")
    starting_position = dict(marco["position"])
    advanced = advance(world, 10)
    marco = next(person for person in advanced["people"] if person["id"] == "person:marco")
    assert marco["activity"].startswith("Walking to") or "Folk Loop" in marco["activity"]
    assert marco["position"] != starting_position
    assert len(marco["route"]) > 2


def test_train_uses_stable_seats_and_alights_at_the_backend_stop():
    world = build_fixture(78)

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
    assert not any(
        person.get("on_train") and person.get("train_arrival_id") == "station:eastgate"
        for person in world["people"]
    )


def test_train_egress_uses_the_same_pedestrian_speed_as_other_walks():
    world = build_fixture(78)
    marco = next(person for person in world["people"] if person["id"] == "person:marco")
    home = next(place for place in world["places"] if place["id"] == marco["home_place_id"])
    work = next(place for place in world["places"] if place["id"] == marco["workplace_id"])
    journey = _train_journey(home, work)

    assert journey is not None
    assert _station_walk_minutes(journey["arrival"], work) == journey["egress_minutes"]
    arrival = journey["arrival"]["position"]
    destination = work["position"]
    assert journey["egress_minutes"] == ceil(
        hypot(destination["x"] - arrival["x"], destination["y"] - arrival["y"]) / 18
    )


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
    world["clock"] = "2031-05-13T16:59:00"
    advance(world, 45)
    assert next_shopper["activity"] == "Shopping at Hearth Market"


def test_grocery_browsing_time_scales_with_household_servings():
    single = {"member_ids": ["person:one"], "grocery_servings_to_buy": 3}
    family_of_four = {
        "member_ids": ["person:one", "person:two", "person:three", "person:four"],
        "grocery_servings_to_buy": 12,
    }

    assert _grocery_browsing_minutes(family_of_four) > _grocery_browsing_minutes(single)


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
    world["clock"] = "2031-05-12T08:14:00"

    advance(world, 1)
    assert elena["needs"]["boredom"] == 42

    world["clock"] = "2031-05-12T16:59:00"
    advance(world, _walking_minutes(bakery, bar) + 1)

    assert elena["activity"] == "Socializing at The Lantern Bar"
    first_position = dict(elena["position"])
    advance(world, 3)
    assert elena["position"] != first_position


def test_evening_staff_cover_bar_and_cinema_shifts():
    world = build_fixture(47)
    marta = next(person for person in world["people"] if person["id"] == "person:marta")
    hugo = next(person for person in world["people"] if person["id"] == "person:hugo")
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
    world["clock"] = "2031-05-12T16:59:00"

    advance(world, _walking_minutes(workplace, cinema) + 1)

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
    advance(world, 80)

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
    elena["needs"].update({"hunger": 20, "rest": 20, "social": 100, "boredom": 0})
    advance(world, 0)

    assert elena["activity"] in {
        "Walking to The Lantern Bar",
        "Meet neighbours at The Lantern Bar",
        "Socializing at The Lantern Bar",
    }


def test_social_outing_routes_from_home_instead_of_teleporting_to_the_bar():
    world = build_fixture(53)
    elena = next(person for person in world["people"] if person["id"] == "person:elena")
    home = next(place for place in world["places"] if place["id"] == elena["home_place_id"])
    elena["position"] = {"x": home["position"]["x"], "y": home["position"]["y"] + 28}
    elena["needs"].update({"hunger": 20, "rest": 20, "social": 100, "boredom": 0})
    world["clock"] = "2031-05-12T18:10:00"
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
