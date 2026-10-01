from copy import deepcopy

from generation.fixture_town import build_fixture
from simulation.staffing import ensure_staffing
from simulation.versions import migrate_snapshot


def staff(world, workplace):
    return {
        person["id"]: person["role"]
        for person in world["people"]
        if person["workplace_id"] == workplace
    }


def assert_staffing(world):
    assert staff(world, "place:library") == {
        "person:lea": "Librarian",
        "person:nora": "Library assistant",
    }
    assert staff(world, "place:clinic") == {
        "person:ana": "Nurse",
        "person:isabel": "Doctor",
    }
    assert staff(world, "place:school")["person:emma"] == "Teaching assistant"
    assert staff(world, "place:post-office")["person:ada"] == "Postal clerk"
    assert staff(world, "place:workshop")["person:oscar"] == "Mechanic"


def test_new_town_has_rebalanced_staffing():
    assert_staffing(build_fixture(42))


def test_old_save_reassigns_staff_once_and_preserves_residents_and_movement():
    world = build_fixture(42)
    world.pop("staffing_version", None)
    old_roles = {
        "person:nora": ("place:library", "Student"),
        "person:emma": ("place:library", "Library assistant"),
        "person:ada": ("place:library", "Librarian"),
        "person:isabel": ("place:clinic", "Nurse"),
        "person:oscar": ("place:clinic", "Nurse"),
    }
    for person in world["people"]:
        if person["id"] in old_roles:
            workplace, role = old_roles[person["id"]]
            person.update(
                workplace_id=workplace, role=role, activity=f"Working as {role.lower()}"
            )
    original = deepcopy(world)
    migrated = migrate_snapshot(world)
    assert_staffing(migrated)
    assert world == original
    assert len(migrated["people"]) == len(original["people"])
    for before, after in zip(original["people"], migrated["people"], strict=True):
        for field in (
            "position",
            "home_place_id",
            "household_id",
            "money_cents",
            "needs",
        ):
            assert after[field] == before[field]
        if before["id"] in old_roles:
            assert not after["activity"].startswith("Working as ")
    assert migrate_snapshot(migrated) == migrated


def test_staffing_preserves_custom_jobs_and_later_reassignments():
    world = build_fixture(42)
    world.pop("staffing_version", None)
    emma = next(p for p in world["people"] if p["id"] == "person:emma")
    emma.update(workplace_id="place:bakery", role="Baker")
    ensure_staffing(world)
    assert emma["workplace_id"] == "place:bakery"
    assert emma["role"] == "Baker"
    emma.update(workplace_id="place:library", role="Library assistant")
    ensure_staffing(world)
    assert emma["workplace_id"] == "place:library"
