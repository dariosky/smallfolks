import json
from datetime import datetime

import pytest

from generation.fixture_town import build_fixture
from simulation.community import ensure_community, fund_community
from simulation.municipal_work import run_municipal_work
from simulation.tick import (
    _at_place,
    _eat_lunch_at_work,
    _position_at,
    _sleep_at_home,
    _walk_from_current_position,
    advance_seconds,
)
from simulation.versions import migrate_snapshot
from simulation.volunteering import run_volunteering


def setup_world():
    world = build_fixture(42)
    now = datetime.fromisoformat("2031-05-19T09:00:00")
    world["clock"] = now.isoformat()
    for person in world["people"]:
        person["needs"].update(hunger=0, rest=0, social=0)
    for place in world["places"]:
        if place["kind"] == "park":
            place["cleanliness"] = 100
    person = next(p for p in world["people"] if p["id"] == "person:maya")
    return world, person, now


def at(person, site):
    person.update(position=_position_at(person, site), target_place_id=site["id"])
    person.pop("route", None)
    person.pop("direct_walk", None)


def run(world, person, now, seconds=15):
    run_municipal_work(
        world,
        person,
        now,
        seconds,
        _walk_from_current_position,
        _at_place,
        _eat_lunch_at_work,
        _sleep_at_home,
    )


def own_project(world, person):
    return next(
        p
        for p in reversed(world["municipal_projects"])
        if p["person_id"] == person["id"] and p["status"] == "active"
    )


def site_for(world, project):
    return next(
        (p for p in world["places"] if p["id"] == project["site_id"]),
        {"id": project["site_id"], "position": project["position"]},
    )


def test_two_planners_two_handymen_in_new_and_existing_saves_without_teleporting():
    world, _, _ = setup_world()
    staff = [p for p in world["people"] if p["workplace_id"] == "place:townhall"]
    assert {p["id"] for p in staff if p["role"] == "Planner"} == {
        "person:sofia",
        "person:eva",
    }
    assert {p["id"] for p in staff if p["role"] == "Town handyman"} == {
        "person:maya",
        "person:sara",
    }
    for person in staff:
        person.update(role="Planner", visual="planner", activity="Working as planner")
    positions = {p["id"]: dict(p["position"]) for p in world["people"]}
    converted = migrate_snapshot(world)
    assert all(
        p["role"] == "Planner" for p in staff
    )  # Read migration does not mutate its input.
    assert sum(p["role"] == "Town handyman" for p in converted["people"]) == 2
    assert {p["id"]: p["position"] for p in converted["people"]} == positions
    assert migrate_snapshot(converted) == converted


@pytest.mark.parametrize(
    "cleanliness,kind", [(49, "park_cleanup"), (50, "library_help")]
)
def test_cleanup_starts_only_below_fifty_percent(cleanliness, kind):
    world, person, now = setup_world()
    park = next(p for p in world["places"] if p["id"] == "place:park")
    park["cleanliness"] = cleanliness
    origin, balance = dict(person["position"]), person["money_cents"]
    run(world, person, now)
    project = own_project(world, person)
    assert project["kind"] == kind
    assert project["worked_seconds"] == 0
    assert person["position"] == origin
    assert person["money_cents"] == balance


def test_two_workers_take_different_dirty_parks_and_receive_only_normal_wages():
    world, person, now = setup_world()
    for place in world["places"]:
        if place["kind"] == "park":
            place["cleanliness"] = 45
    other = next(p for p in world["people"] if p["id"] == "person:sara")
    fund_community(world, now)
    run(world, person, now)
    run(world, other, now)
    project, other_project = own_project(world, person), own_project(world, other)
    assert project["site_id"] != other_project["site_id"]
    site = site_for(world, project)
    at(person, site)
    before = person["money_cents"], world["economy"]["treasury_cents"]
    for _ in range(4):
        run(world, person, now, 900)
    assert project["status"] == "completed"
    assert site["cleanliness"] == 85
    assert person["money_cents"] == before[0] + 600  # Half of the ordinary €12/hour.
    assert world["economy"]["treasury_cents"] == before[1] - 1200
    assert world["economy"]["community_work_cents"] == 0
    assert world["volunteering_projects"] == []


def test_tree_progress_is_saved_and_preempted_by_urgent_cleanup_then_resumed():
    world, person, now = setup_world()
    library = next(p for p in world["places"] if p["id"] == "place:library")
    library["municipal_library_help_date"] = now.date().isoformat()
    run(world, person, now)
    project = own_project(world, person)
    assert project["kind"] == "tree_planting"
    site = site_for(world, project)
    at(person, site)
    run(world, person, now, 900)
    world = json.loads(json.dumps(world))
    person = next(p for p in world["people"] if p["id"] == person["id"])
    project = next(
        p for p in world["municipal_projects"] if p["kind"] == "tree_planting"
    )
    park = next(p for p in world["places"] if p["id"] == "place:park")
    park["cleanliness"] = 45
    run(world, person, now)
    cleanup = own_project(world, person)
    assert cleanup["kind"] == "park_cleanup"
    assert project["worked_seconds"] == 900
    at(person, park)
    for _ in range(4):
        run(world, person, now, 900)
    assert cleanup["status"] == "completed"
    at(person, site_for(world, project))
    for _ in range(15):
        run(world, person, now, 900)
    assert project["status"] == "completed"
    assert len(world["planted_trees"]) == 1
    assert world["planted_trees"][0]["id"] == project["id"]


def test_companionship_precedes_library_and_planting_and_reduces_social_need():
    world, person, now = setup_world()
    recipient = next(p for p in world["people"] if p["id"] == "person:marta")
    recipient["needs"]["social"] = 80
    home = next(p for p in world["places"] if p["id"] == recipient["home_place_id"])
    at(recipient, home)
    recipient["activity"] = "Reading at home"
    run(world, person, now)
    project = own_project(world, person)
    assert (
        project["kind"] == "social_visit" and project["recipient_id"] == recipient["id"]
    )
    at(person, home)
    for _ in range(4):
        run(world, person, now, 900)
    assert project["status"] == "completed"
    assert recipient["needs"]["social"] == 45
    assert recipient["municipal_visit_date"] == now.date().isoformat()
    run(world, person, now)
    assert own_project(world, person)["kind"] == "library_help"


def test_social_visit_does_not_progress_when_recipient_leaves():
    world, person, now = setup_world()
    recipient = next(p for p in world["people"] if p["id"] == "person:marta")
    recipient["needs"]["social"] = 80
    home = next(p for p in world["places"] if p["id"] == recipient["home_place_id"])
    at(recipient, home)
    recipient["activity"] = "Reading at home"
    run(world, person, now)
    project = own_project(world, person)
    at(person, home)
    run(world, person, now, 900)
    assert recipient["needs"]["social"] == 72
    world = json.loads(json.dumps(world))
    person = next(p for p in world["people"] if p["id"] == person["id"])
    recipient = next(p for p in world["people"] if p["id"] == recipient["id"])
    project = own_project(world, person)
    recipient["target_place_id"] = "place:lantern-bar"
    run(world, person, now)
    assert project["status"] == "cancelled"
    assert project["worked_seconds"] == 900
    assert recipient["needs"]["social"] == 72


def test_library_help_is_daily_and_planting_is_the_fallback():
    world, person, now = setup_world()
    run(world, person, now)
    project = own_project(world, person)
    assert project["kind"] == "library_help"
    library = site_for(world, project)
    at(person, library)
    for _ in range(4):
        run(world, person, now, 900)
    assert library["library_help_sessions"] == 1
    run(world, person, now)
    assert own_project(world, person)["kind"] == "tree_planting"


def test_urgent_hunger_and_lunch_pause_on_site_progress_and_pay():
    world, person, now = setup_world()
    run(world, person, now)
    project = own_project(world, person)
    at(person, site_for(world, project))
    person["needs"]["hunger"] = 90
    balance = person["money_cents"]
    run(world, person, now, 900)
    assert project["worked_seconds"] == 0 and person["money_cents"] == balance
    person["needs"].update(hunger=40)
    run(world, person, now.replace(hour=12), 900)
    assert project["worked_seconds"] == 0 and person["money_cents"] == balance
    person["needs"]["hunger"] = 0
    run(world, person, now, 900)
    assert project["worked_seconds"] == 900


@pytest.mark.parametrize("timestamp", ["2031-05-17T09:00:00", "2031-05-19T17:00:00"])
def test_days_off_and_shift_end_do_not_assign_or_pay(timestamp):
    world, person, _ = setup_world()
    before = person["money_cents"]
    run(world, person, datetime.fromisoformat(timestamp), 900)
    assert world["municipal_projects"] == []
    assert person["money_cents"] == before


def test_assignments_and_volunteers_do_not_share_parcels_or_active_sites():
    world, person, now = setup_world()
    park = next(p for p in world["places"] if p["id"] == "place:park")
    park["cleanliness"] = 45
    run(world, person, now)
    assert own_project(world, person)["site_id"] == park["id"]
    volunteer = world["people"][0]
    volunteer.update(
        nature_inclination=0, community_inclination=1, library_inclination=0
    )
    assert run_volunteering(
        world, volunteer, now, 15, 1080, True, _walk_from_current_position, _at_place
    )
    assert world["volunteering_projects"][0]["parcel_id"] != park["id"]


def test_normal_ticks_route_handymen_to_work_instead_of_the_planning_desk():
    world, person, _ = setup_world()
    park = next(p for p in world["places"] if p["id"] == "place:park")
    park["cleanliness"] = 45
    person.update(preferred_wake_minute=480, day_off_sleep_in_minutes=0)
    origin = dict(person["position"])
    advance_seconds(world, 15)
    assert person["activity"].startswith("Walking to town work:")
    assert person["position"] == origin
    project = own_project(world, person)
    assert project["kind"] == "park_cleanup" and project["worked_seconds"] == 0
    at(person, park)
    before = person["money_cents"]
    advance_seconds(world, 15 * 60)
    assert project["worked_seconds"] == 900
    assert person["money_cents"] == before + 150


def test_zero_time_does_not_create_assignments():
    world, person, now = setup_world()
    run(world, person, now, 0)
    assert world["municipal_projects"] == []
    ensure_community(world)
    assert person["role"] == "Town handyman"


def test_urgent_rest_walks_to_townhall_without_teleporting_or_paying():
    world, person, now = setup_world()
    run(world, person, now)
    project = own_project(world, person)
    at(person, site_for(world, project))
    origin, balance = dict(person["position"]), person["money_cents"]
    person["needs"]["rest"] = 90
    run(world, person, now)
    assert person["activity"] == "Walking to Town Hall to rest"
    assert person["position"] == origin
    assert project["worked_seconds"] == 0 and person["money_cents"] == balance
    townhall = next(p for p in world["places"] if p["id"] == "place:townhall")
    at(person, townhall)
    run(world, person, now, 900)
    assert person["activity"] == "Resting at Town Hall"
    assert project["worked_seconds"] == 0 and person["money_cents"] == balance
