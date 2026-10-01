from copy import deepcopy

import pytest

from generation.fixture_town import build_fixture
from simulation.versions import migrate_snapshot


@pytest.mark.parametrize(
    "key,reason",
    [
        ("volunteering_projects", "volunteering"),
        ("municipal_projects", "town_employee"),
    ],
)
def test_old_tree_history_is_recovered_without_mutating_source(key, reason):
    world = build_fixture(42)
    person = world["people"][0]
    world["planted_trees"] = [{"id": "old-tree", "position": {"x": 100, "y": 100}}]
    world[key] = [
        {
            "id": "old-tree",
            "kind": "tree_planting",
            "status": "completed",
            "person_id": person["id"],
            "completed_at": "2031-05-12T11:30:00",
        }
    ]
    before = deepcopy(world)
    migrated = migrate_snapshot(world)
    tree = migrated["planted_trees"][0]
    assert tree["planting_reason"] == reason
    assert tree["planted_by_id"] == person["id"]
    assert tree["planted_by_name"] == person["name"]
    assert tree["planted_at"] == "2031-05-12T11:30:00"
    assert world == before
    assert migrate_snapshot(migrated) == migrated


def test_scenery_and_untraceable_trees_keep_unknown_history():
    world = build_fixture(42)
    world.pop("scenery_trees")
    world["planted_trees"] = [{"id": "untraceable", "position": {"x": 10, "y": 10}}]
    migrated = migrate_snapshot(world)
    assert (
        len(
            [
                t
                for t in migrated["scenery_trees"]
                if t["id"].startswith("tree:scenery:")
            ]
        )
        == 12
    )
    assert all(t["planted_at"] is None for t in migrated["scenery_trees"])
    assert migrated["planted_trees"][0]["planting_reason"] is None
    assert migrated["planted_trees"][0]["planted_by_id"] is None
