import pytest

from generation.fixture_town import build_fixture
from generation.validators import validate_place_layout
from simulation.tick import _position_at, advance_seconds
from simulation.versions import migrate_snapshot


def at(person, place):
    person.pop("route", None)
    person.pop("direct_walk", None)
    person["position"] = _position_at(person, place)
    person["target_place_id"] = place["id"]


@pytest.mark.parametrize("day", [17, 18])
def test_weekend_jobs_and_wages(day):
    world = build_fixture(42)
    world["clock"] = f"2031-05-{day}T10:00:00"  # Saturday / Sunday
    for person in world["people"]:
        work = next(p for p in world["places"] if p["id"] == person["workplace_id"])
        at(person, work)
        person["needs"].update(hunger=0, rest=0)
    teacher = next(p for p in world["people"] if p["role"] == "Teacher")
    nurse = next(p for p in world["people"] if p["role"] == "Nurse")
    balance = teacher["money_cents"]
    advance_seconds(world, 15)
    assert not teacher["activity"].startswith("Working")
    assert teacher["money_cents"] == balance
    assert nurse["activity"] == "Working as nurse"
    shopkeeper = next(p for p in world["people"] if p["role"] == "Shopkeeper")
    assert shopkeeper["activity"].startswith("Working") == (day == 17)
    world["clock"] = "2031-05-19T10:00:00"  # Monday
    at(teacher, next(p for p in world["places"] if p["id"] == teacher["workplace_id"]))
    advance_seconds(world, 15)
    assert teacher["activity"] == "Working as teacher"


@pytest.mark.parametrize("hour, slot", [(12, "lunch"), (19, "dinner")])
def test_restaurant_meal_is_paid_once_and_reduces_hunger(hour, slot):
    world = build_fixture(42)
    world["clock"] = f"2031-05-17T{hour}:00:00"
    restaurant = next(p for p in world["places"] if p["id"] == "place:restaurant")
    staff = next(p for p in world["people"] if p["id"] == f"person:restaurant-{slot}")
    at(staff, restaurant)
    staff["needs"].update(hunger=0, rest=0)
    staff["activity"] = "Working as chef"
    guest = next(p for p in world["people"] if p["role"] == "Teacher")
    at(guest, restaurant)
    guest["restaurant_inclination"] = 1
    guest["needs"].update(hunger=85, rest=0)
    before = guest["money_cents"]
    advance_seconds(world, 15)
    assert guest["activity"] == f"Eating {slot} at The Olive Table"
    assert guest["money_cents"] == before - 1500
    hunger = guest["needs"]["hunger"]
    advance_seconds(world, 5 * 60)
    assert guest["money_cents"] == before - 1500
    assert guest["needs"]["hunger"] < hunger


def test_restaurant_upgrade_is_additive_and_layout_valid():
    world = build_fixture(42)
    validate_place_layout(world["places"])
    world["places"] = [p for p in world["places"] if p["id"] != "place:restaurant"]
    upgraded = migrate_snapshot(world)
    assert not any(p["id"] == "place:restaurant" for p in world["places"])
    assert (
        sum(p["id"] == "place:restaurant" for p in migrate_snapshot(upgraded)["places"])
        == 1
    )
    assert len(migrate_snapshot(upgraded)["people"]) == len(upgraded["people"])


@pytest.mark.parametrize("blocked", ["money", "staff", "preference"])
def test_restaurant_requires_affordability_staff_and_preference(blocked):
    world = build_fixture(42)
    world["clock"] = "2031-05-17T12:00:00"
    restaurant = next(p for p in world["places"] if p["id"] == "place:restaurant")
    guest = next(p for p in world["people"] if p["role"] == "Teacher")
    guest["needs"].update(hunger=85, rest=0)
    guest["restaurant_inclination"] = 1
    staff = next(p for p in world["people"] if p["id"] == "person:restaurant-lunch")
    at(staff, restaurant)
    staff["activity"] = "Working as chef"
    staff["needs"].update(hunger=0, rest=0)
    if blocked == "money":
        guest["money_cents"] = 0
    elif blocked == "staff":
        staff["activity"] = "At home"
        staff["work_days"] = []
    else:
        guest["restaurant_inclination"] = 0
    advance_seconds(world, 15)
    assert "restaurant_plan" not in guest


def test_restaurant_walk_survives_reload_without_prepayment():
    world = build_fixture(42)
    world["clock"] = "2031-05-17T12:00:00"
    restaurant = next(p for p in world["places"] if p["id"] == "place:restaurant")
    staff = next(p for p in world["people"] if p["id"] == "person:restaurant-lunch")
    at(staff, restaurant)
    staff["activity"] = "Working as chef"
    staff["needs"].update(hunger=0, rest=0)
    guest = next(p for p in world["people"] if p["role"] == "Teacher")
    guest["needs"].update(hunger=85, rest=0)
    guest["restaurant_inclination"] = 1
    before = guest["money_cents"]
    advance_seconds(world, 15)
    assert guest["activity"] == "Walking to The Olive Table"
    assert guest["money_cents"] == before
    loaded = migrate_snapshot(world)
    saved_guest = next(p for p in loaded["people"] if p["id"] == guest["id"])
    assert saved_guest["restaurant_plan"] == guest["restaurant_plan"]
    assert saved_guest["position"] == guest["position"]


def test_personal_sleep_preferences_survive_migration():
    from simulation.schedules import ensure_schedules

    world = build_fixture(710)
    profiles = [(p['preferred_wake_minute'], p['sleep_duration_minutes']) for p in world['people']]
    assert len(set(profiles)) > 10
    world['people'][0]['preferred_wake_minute'] = 555
    ensure_schedules(world)
    assert world['people'][0]['preferred_wake_minute'] == 555
    migrated = migrate_snapshot(world)
    assert migrated['people'][0]['preferred_wake_minute'] == 555


def test_sleep_windows_allow_late_shifts_and_weekend_sleep_ins():
    from datetime import datetime

    from simulation.schedules import sleep_window
    from simulation.tick import _walking_minutes

    world = build_fixture(711)
    places = {p['id']: p for p in world['places']}
    people = {p['id']: p for p in world['people']}
    teacher = people['person:tom']
    bartender = people['person:marta']
    windows = {}
    for person in (teacher, bartender):
        work = places[person['workplace_id']]
        commute = _walking_minutes(places[person['home_place_id']], work)
        bed, wake = sleep_window(person, work, datetime.fromisoformat("2031-05-13T03:00:00"), commute)
        assert wake.hour * 60 + wake.minute + commute + person['morning_preparation_minutes'] <= person.get('shift_start_minute', 480)
        windows[person['id']] = bed, wake
    bed, wake = windows[bartender['id']]
    assert bed.date() == wake.date()  # After coming home from the 23:00 shift.
    assert wake.hour >= 9
    _, weekday_wake = windows[teacher['id']]
    _, weekend_wake = sleep_window(teacher, places[teacher['workplace_id']], datetime.fromisoformat("2031-05-17T03:00:00"), 30)
    assert weekend_wake.hour >= 8
    assert weekend_wake.time() > weekday_wake.time()


def test_late_workers_stay_asleep_while_early_workers_prepare_for_work():
    world = build_fixture(712)
    world['clock'] = '2031-05-13T08:00:00'
    world['pets'][0]['last_walk_at'] = world['clock']
    for person in world['people']:
        person['needs'].update(rest=0, hunger=0)
    advance_seconds(world, 0)
    bartender = next(p for p in world['people'] if p['id'] == 'person:marta')
    teacher = next(p for p in world['people'] if p['id'] == 'person:tom')
    assert bartender['activity'] == 'Sleeping at home'
    assert bartender['next_commitment'].startswith('Wake at ')
    assert teacher['activity'] != 'Sleeping at home'
