import json
from datetime import datetime, timedelta

import pytest

from generation.fixture_town import build_fixture
from simulation.community import (
    SUPPORT_CENTS,
    advance_community_conditions,
    ensure_community,
    fund_community,
)
from simulation.economy import pay_work_seconds, transfer
from simulation.tick import (
    _at_place,
    _position_at,
    _walk_from_current_position,
    advance_seconds,
)
from simulation.versions import migrate_snapshot
from simulation.volunteering import TASKS, run_volunteering


def setup_world():
    world = build_fixture(42)
    now = datetime.fromisoformat("2031-05-19T09:00:00")
    world["clock"] = now.isoformat()
    person = world["people"][0]
    person["needs"].update(hunger=0, rest=0, boredom=70)
    ensure_community(world)
    return world, person, now


def close_job(world, person):
    next(p for p in world["places"] if p["id"] == person["workplace_id"])["business"][
        "status"
    ] = "bankrupt"


def total_money(world):
    economy = world["economy"]
    return (
        sum(
            value
            for key, value in economy.items()
            if key
            in {
                "treasury_cents",
                "outside_cents",
                "regional_customers_cents",
                "regional_grants_cents",
                "community_work_cents",
                "bank_cents",
                "construction_cents",
            }
        )
        + sum(p["money_cents"] for p in world["people"])
        + sum(h["money_cents"] for h in world["households"])
        + sum(
            p.get("business", {}).get("balance_cents", 0)
            + p.get("dealership", {}).get("balance_cents", 0)
            for p in world["places"]
        )
    )


def test_support_is_once_daily_shared_and_separate_from_earned_income_after_reload():
    world, person, now = setup_world()
    close_job(world, person)
    household = next(
        h for h in world["households"] if h["id"] == person["household_id"]
    )
    before = person["money_cents"], household["money_cents"], total_money(world)
    fund_community(world, now.replace(hour=7))
    assert "support_paid_date" not in person
    fund_community(world, now)
    assert person["money_cents"] == before[0] + 1200
    assert household["money_cents"] == before[1] + 1200
    assert person.get("income_history", {}) == {}
    assert total_money(world) == before[2]
    world = json.loads(json.dumps(world))
    world["economy"]["ledger"] = []  # Payment survives even after ledger truncation.
    fund_community(world, now + timedelta(hours=3))
    assert world["people"][0]["support_total_cents"] == SUPPORT_CENTS
    fund_community(world, now + timedelta(days=1))
    assert world["people"][0]["support_total_cents"] == 2 * SUPPORT_CENTS


@pytest.mark.parametrize("percent", [0, 30, 100])
def test_support_sharing_and_midday_closure(percent):
    world, person, now = setup_world()
    world["economy"]["household_contribution_percent"] = percent
    fund_community(world, now)
    assert "support_paid_date" not in person
    close_job(world, person)
    before = person["money_cents"]
    fund_community(world, now.replace(hour=13))
    assert person["money_cents"] == before + SUPPORT_CENTS * (100 - percent) // 100
    next(p for p in world["places"] if p["id"] == person["workplace_id"])["business"][
        "status"
    ] = "open"
    fund_community(world, now + timedelta(days=1))
    assert person["support_total_cents"] == SUPPORT_CENTS


def test_students_and_days_off_are_not_unemployment():
    world, person, now = setup_world()
    person["work_days"] = []
    fund_community(world, now)
    assert "support_paid_date" not in person
    person["visual"] = "student"
    close_job(world, person)
    fund_community(world, now)
    assert "support_paid_date" not in person


def test_depleted_treasury_grants_are_conserved_and_do_not_repeat_on_spending():
    world, person, now = setup_world()
    world["economy"]["treasury_cents"] = 100
    close_job(world, person)
    before = total_money(world)
    fund_community(world, now)
    grant = world["economy"]["regional_grant_total_cents"]
    assert grant > 0
    public_worker = next(p for p in world["people"] if p["role"] == "Teacher")
    pay_work_seconds(world, public_worker, 900, now)
    fund_community(world, now)
    assert world["economy"]["regional_grant_total_cents"] == grant
    assert total_money(world) == before
    assert all(e["amount_cents"] >= 0 for e in world["economy"]["ledger"])


def test_insufficient_external_funding_does_not_mark_support_paid():
    world, person, now = setup_world()
    close_job(world, person)
    world["economy"].update(treasury_cents=0, regional_grants_cents=0)
    fund_community(world, now)
    assert "support_paid_date" not in person
    assert world["economy"]["treasury_cents"] == 0


@pytest.mark.parametrize("kind", list(TASKS))
def test_each_task_walks_reserves_pay_and_has_a_persistent_outcome(kind):
    world, person, now = setup_world()
    person.update(nature_inclination=0, community_inclination=0, library_inclination=0)
    preference = {
        "tree_planting": "nature",
        "community_gardening": "nature",
        "park_cleanup": "community",
        "library_help": "library",
    }[kind]
    person[f"{preference}_inclination"] = 0.6 if kind == "community_gardening" else 1
    before = (
        person["money_cents"],
        world["economy"]["treasury_cents"],
        total_money(world),
    )
    assert run_volunteering(
        world, person, now, 15, 1080, True, _walk_from_current_position, _at_place
    )
    project = world["volunteering_projects"][0]
    assert project["kind"] == kind
    assert project["worked_seconds"] == 0
    assert world["economy"]["treasury_cents"] == before[1] - project["wage_cents"]
    # Reserved money is inaccessible to unrelated treasury transfers.
    world["economy"]["treasury_cents"] = 0
    assert not transfer(world, "treasury", person["id"], 1, "Other expense", now)
    world["economy"]["treasury_cents"] = before[1] - project["wage_cents"]
    world = json.loads(json.dumps(world))
    person, project = world["people"][0], world["volunteering_projects"][0]
    site = next(
        (p for p in world["places"] if p["id"] == project["parcel_id"]),
        {"id": project["parcel_id"], "position": project["position"]},
    )
    person.update(position=_position_at(person, site), target_place_id=site["id"])
    person.pop("route", None)
    person.pop("direct_walk", None)
    person["needs"]["hunger"] = 90
    assert not run_volunteering(
        world, person, now, 15, 1080, True, _walk_from_current_position, _at_place
    )
    assert project["worked_seconds"] == 0
    person["needs"]["hunger"] = 0
    person["evening_plan"] = {"date": now.date().isoformat(), "phase": "return"}
    assert not run_volunteering(
        world, person, now, 15, 1080, True, _walk_from_current_position, _at_place
    )
    assert project["worked_seconds"] == 0
    person.pop("evening_plan")
    assert run_volunteering(
        world,
        person,
        now,
        project["required_seconds"],
        1080,
        True,
        _walk_from_current_position,
        _at_place,
    )
    assert project["status"] == "completed"
    assert person["money_cents"] == before[0] + project["wage_cents"] // 2
    assert world["economy"]["community_work_cents"] == 0
    assert total_money(world) == before[2]
    assert not run_volunteering(
        world, person, now, 15, 1080, True, _walk_from_current_position, _at_place
    )
    if kind == "tree_planting":
        assert len(world["planted_trees"]) == 1
    elif kind == "community_gardening":
        assert len(world["community_gardens"]) == 1
    elif kind == "park_cleanup":
        assert site["cleanliness"] == 100 and site["cleanup_sessions"] == 1
        advance_community_conditions(world, 3600)
        assert site["cleanliness"] == 99
    else:
        assert site["library_help_sessions"] == 1


def test_short_tasks_fit_around_shifts_with_travel_and_no_nature_gate():
    world, person, now = setup_world()
    person.update(
        nature_inclination=0,
        community_inclination=1,
        library_inclination=0,
        volunteering_choice={"date": now.date().isoformat(), "accepted": True},
    )
    # 60 work + 10 outbound + 10 return + 15 buffer = 95 minutes.
    assert not run_volunteering(
        world,
        person,
        now,
        15,
        630,
        False,
        _walk_from_current_position,
        _at_place,
        lambda *_: 10,
    )
    assert run_volunteering(
        world,
        person,
        now,
        15,
        640,
        False,
        _walk_from_current_position,
        _at_place,
        lambda *_: 10,
    )
    assert world["volunteering_projects"][0]["kind"] == "park_cleanup"
    assert not run_volunteering(
        world, person, now, 15, 540, False, _walk_from_current_position, _at_place
    )


def test_daily_decline_is_stable_across_repeated_ticks_and_reload():
    world, person, now = setup_world()
    person["volunteering_choice"] = {"date": now.date().isoformat(), "accepted": False}
    for hour in (9, 10, 11):
        assert not run_volunteering(
            world,
            person,
            now.replace(hour=hour),
            15,
            1080,
            False,
            _walk_from_current_position,
            _at_place,
        )
        world = json.loads(json.dumps(world))
        person = world["people"][0]
    assert world["volunteering_projects"] == []


def test_library_help_only_runs_in_scheduled_hours_and_has_one_active_slot():
    world, person, now = setup_world()
    person.update(nature_inclination=0, community_inclination=0, library_inclination=1)
    assert run_volunteering(
        world, person, now, 15, 1080, True, _walk_from_current_position, _at_place
    )
    other = world["people"][1]
    other.update(nature_inclination=0, community_inclination=0, library_inclination=1)
    other["needs"].update(hunger=0, rest=0)
    assert run_volunteering(
        world, other, now, 15, 1080, True, _walk_from_current_position, _at_place
    )
    assert world["volunteering_projects"][1]["kind"] != "library_help"
    assert not run_volunteering(
        world,
        person,
        now.replace(hour=17),
        15,
        1080,
        True,
        _walk_from_current_position,
        _at_place,
    )
    assert world["volunteering_projects"][0]["worked_seconds"] == 0


def test_legacy_project_keeps_terms_and_reserves_only_on_advance():
    world, person, now = setup_world()
    project = {
        "id": "planting:1",
        "person_id": person["id"],
        "parcel_id": "parcel:100:100",
        "position": {"x": 100, "y": 100},
        "status": "active",
        "worked_seconds": 120,
        "required_seconds": 14400,
        "wage_cents": 2400,
    }
    world["volunteering_projects"] = [project]
    before = world["economy"]["treasury_cents"]
    migrated = migrate_snapshot(world)
    assert world["volunteering_projects"][0] == project
    assert migrated["economy"]["treasury_cents"] == before
    assert migrated["volunteering_projects"][0] == project
    fund_community(migrated, now)
    assert migrated["volunteering_projects"][0]["payment_reserved"]
    assert migrated["volunteering_projects"][0]["worked_seconds"] == 120
    assert migrated["economy"]["community_work_cents"] == 2400
    fund_community(migrated, now)
    assert migrated["economy"]["community_work_cents"] == 2400
    legacy_person = migrated["people"][0]
    legacy_site = {"id": project["parcel_id"], "position": project["position"]}
    legacy_person.update(
        position=_position_at(legacy_person, legacy_site),
        target_place_id=legacy_site["id"],
    )
    before_pay = legacy_person["money_cents"]
    assert run_volunteering(
        migrated,
        legacy_person,
        now,
        14400 - 120,
        1080,
        True,
        _walk_from_current_position,
        _at_place,
    )
    assert migrated["volunteering_projects"][0]["status"] == "completed"
    assert legacy_person["money_cents"] == before_pay + 1200
    assert migrated["economy"]["community_work_cents"] == 0
    assert migrated["planted_trees"][0]["id"] == "planting:1"


def test_zero_time_advance_does_not_award_grants_support_or_tasks():
    world, person, _ = setup_world()
    close_job(world, person)
    world["economy"]["treasury_cents"] = 0
    advance_seconds(world, 0)
    assert world["economy"]["regional_grant_total_cents"] == 0
    assert "support_paid_date" not in person
    assert world["volunteering_projects"] == []


def test_strong_community_interest_motivates_existing_zero_boredom_residents():
    world, person, now = setup_world()
    person["needs"]["boredom"] = 0
    person.update(
        nature_inclination=0,
        community_inclination=1,
        library_inclination=0,
        volunteering_choice={"date": now.date().isoformat(), "accepted": True},
    )
    assert run_volunteering(
        world, person, now, 15, 1080, False, _walk_from_current_position, _at_place
    )
    assert world["volunteering_projects"][0]["kind"] == "park_cleanup"


def test_uninterested_resident_needs_boredom_before_considering_work():
    world, person, now = setup_world()
    person["needs"]["boredom"] = 0
    person.update(
        nature_inclination=0,
        community_inclination=0,
        library_inclination=0,
        volunteering_choice={"date": now.date().isoformat(), "accepted": True},
    )
    assert not run_volunteering(
        world, person, now, 15, 1080, False, _walk_from_current_position, _at_place
    )
    person["needs"]["boredom"] = 20
    assert run_volunteering(
        world, person, now, 15, 1080, False, _walk_from_current_position, _at_place
    )
