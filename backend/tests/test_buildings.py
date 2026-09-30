from datetime import datetime

from generation.fixture_town import build_fixture
from simulation.buildings import update_building_status
from simulation.economy import charge_daily_overhead, ensure_economy, take_over_business
from simulation.tick import _position_at, advance_seconds
from simulation.versions import migrate_snapshot


def place(world, place_id):
    return next(p for p in world["places"] if p["id"] == place_id)


def test_library_weekend_closure_has_exact_schedule_and_reopening():
    world = build_fixture(42)
    world["clock"] = "2031-05-17T10:00:00"
    update_building_status(world)
    state = place(world, "place:library")["operating_state"]
    assert state["status"] == "Closed — day off"
    assert state["closed_since"] == "2031-05-16T17:00:00"
    assert state["next_open_at"] == "2031-05-19T08:00:00"
    assert migrate_snapshot(world)["places"] == world["places"]


def test_building_stops_when_staff_leave_and_reopens_when_they_work():
    world = build_fixture(42)
    world["clock"] = "2031-05-12T10:00:00"
    library = place(world, "place:library")
    workers = [p for p in world["people"] if p["workplace_id"] == library["id"]]
    for worker in workers:
        worker.update(
            position=_position_at(worker, library),
            target_place_id=library["id"],
            activity="Working as librarian",
        )
        worker["needs"].update(hunger=0, rest=0)
    update_building_status(world, observed=True)
    assert library["operating_state"]["is_open"]
    for worker in workers:
        worker["activity"] = "Eating lunch at work"
    update_building_status(world, observed=True)
    assert not library["operating_state"]["is_open"]
    assert library["operating_state"]["closed_since"] == world["clock"]
    world["clock"] = "2031-05-12T10:05:00"
    update_building_status(world, observed=True)
    assert library["operating_state"]["closed_since"] == "2031-05-12T10:00:00"
    advance_seconds(world, 15)
    assert library["operating_state"]["is_open"]
    assert library["operating_state"]["closed_since"] is None


def test_bankruptcy_time_survives_events_and_takeover_reopens_schedule():
    world = build_fixture(42)
    world["clock"] = "2031-05-13T00:00:00"
    bakery = place(world, "place:bakery")
    bakery["business"]["balance_cents"] = 0
    charge_daily_overhead(world, datetime.fromisoformat(world["clock"]))
    world["events"] = []
    update_building_status(world)
    state = bakery["operating_state"]
    assert state["status"] == "Closed — bankrupt"
    assert state["closed_since"] == world["clock"]
    assert state["next_open_at"] is None
    loaded = migrate_snapshot(world)
    assert place(loaded, bakery["id"])["operating_state"] == state
    buyer = world["people"][0]
    buyer["money_cents"] = 100_000
    take_over_business(
        world, bakery["id"], buyer["id"], 100, datetime.fromisoformat(world["clock"])
    )
    update_building_status(world)
    assert bakery["operating_state"]["status"] == "Closed"
    assert "closed_at" not in bakery["business"]


def test_legacy_bankruptcy_uses_known_event_or_reports_unknown_time():
    world = build_fixture(42)
    bakery = place(world, "place:bakery")
    bakery["business"]["status"] = "bankrupt"
    world["events"] = [
        {
            "at": "2031-05-11T00:00",
            "summary": "Rosa Bakery closed after running out of money.",
        }
    ]
    ensure_economy(world)
    update_building_status(world)
    assert bakery["operating_state"]["closed_since"] == "2031-05-11T00:00"
    bakery["business"].pop("closed_at")
    world["events"] = []
    ensure_economy(world)
    update_building_status(world)
    assert bakery["operating_state"]["closed_since"] is None
