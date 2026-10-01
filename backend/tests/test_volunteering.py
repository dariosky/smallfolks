from copy import deepcopy
from datetime import datetime

from generation.fixture_town import build_fixture
from simulation.tick import (
    _at_place,
    _position_at,
    _walk_from_current_position,
    advance_seconds,
)
from simulation.volunteering import PLANTING_SECONDS, empty_parcels, run_volunteering


def test_unemployed_resident_walks_plants_and_is_paid_once_after_four_hours():
    world = build_fixture(42)
    person = next(p for p in world["people"] if p["id"] == "person:elena")
    world["clock"] = "2031-05-17T08:00:00"
    next(p for p in world["places"] if p["id"] == person["workplace_id"])["business"][
        "status"
    ] = "bankrupt"
    person.update(
        preferred_wake_minute=480, day_off_sleep_in_minutes=0, nature_inclination=1
    )
    person["needs"].update(hunger=0, rest=0)
    origin = dict(person["position"])
    advance_seconds(world, 15)
    project = next(
        p for p in world["volunteering_projects"] if p["person_id"] == person["id"]
    )
    assert person["position"] == origin
    assert person["activity"].startswith("Walking to a town hall")
    assert project["worked_seconds"] == 0
    world = deepcopy(world)  # JSON snapshot fields carry all project progress.
    person = next(p for p in world["people"] if p["id"] == person["id"])
    project = next(
        p for p in world["volunteering_projects"] if p["person_id"] == person["id"]
    )
    site = {"id": project["parcel_id"], "position": project["position"]}
    person["position"] = _position_at(person, site)
    person["target_place_id"] = site["id"]
    person.pop("direct_walk", None)
    person.pop("route", None)
    now = datetime.fromisoformat(world["clock"])
    before = person["money_cents"]
    treasury = world["economy"]["treasury_cents"]
    escrow = world["economy"]["community_work_cents"]
    args = (world, person, now)
    run_volunteering(
        *args, PLANTING_SECONDS - 15, 1080, True, _walk_from_current_position, _at_place
    )
    assert person["money_cents"] == before
    run_volunteering(*args, 15, 1080, True, _walk_from_current_position, _at_place)
    assert project["status"] == "completed"
    assert person["money_cents"] == before + 1200
    assert world["economy"]["treasury_cents"] == treasury
    assert world["economy"]["community_work_cents"] == escrow - 2400
    assert len(world["planted_trees"]) == 1
    assert not run_volunteering(
        *args, 15, 1080, True, _walk_from_current_position, _at_place
    )
    assert person["money_cents"] == before + 1200


def test_nature_preference_free_time_needs_and_parcel_reservations():
    world = build_fixture(42)
    now = datetime.fromisoformat("2031-05-17T09:00:00")
    people = world["people"][:2]
    for person in people:
        person["nature_inclination"] = 1
        person["volunteering_choice"] = {
            "date": now.date().isoformat(),
            "accepted": True,
        }
        person["needs"].update(hunger=0, rest=0, boredom=70)
    person = people[0]

    def run(person, until=1080):
        return run_volunteering(
            world, person, now, 15, until, False, _walk_from_current_position, _at_place
        )

    assert not run(person, 600)
    person["volunteering_choice"]["accepted"] = False
    assert not run(person)
    person["volunteering_choice"]["accepted"] = True
    person["needs"]["hunger"] = 90
    assert not run(person)
    person["needs"]["hunger"] = 0
    assert run(person)
    assert run(people[1])
    projects = world["volunteering_projects"]
    assert projects[0]["parcel_id"] != projects[1]["parcel_id"]
    assert all(
        p["parcel_id"] in {s["id"] for s in empty_parcels(world)} for p in projects
    )
    worked = projects[0]["worked_seconds"]
    person["needs"]["rest"] = 90
    assert not run(person)
    assert projects[0]["worked_seconds"] == worked


def test_planting_completes_through_normal_ticks():
    world = build_fixture(42)
    world["clock"] = "2031-05-17T08:00:00"
    person = next(p for p in world["people"] if p["role"] == "Teacher")
    person.update(preferred_wake_minute=480, day_off_sleep_in_minutes=0)
    person["nature_inclination"] = 1
    person["volunteering_choice"] = {"date": "2031-05-17", "accepted": True}
    person["needs"].update(hunger=0, rest=0, boredom=70)
    advance_seconds(world, 6 * 60 * 60)
    projects = [
        p for p in world["volunteering_projects"] if p["person_id"] == person["id"]
    ]
    assert len(projects) == 1
    assert projects[0]["status"] == "completed"
    assert projects[0]["worked_seconds"] == PLANTING_SECONDS
    assert any(t["id"] == projects[0]["id"] for t in world["planted_trees"])
