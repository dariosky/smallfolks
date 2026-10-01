"""Durable planting history, including recovery from older project records."""

SCENERY_POSITIONS = (
    (45, 65),
    (335, 80),
    (330, 290),
    (410, 130),
    (445, 320),
    (675, 180),
    (755, 260),
    (910, 120),
    (1110, 410),
    (920, 550),
    (1090, 610),
    (380, 610),
)


def planting_record(project, person, now, reason):
    return {
        "id": project["id"],
        "kind": "tree",
        "name": "Town tree",
        "position": dict(project["position"]),
        "planted_at": now.isoformat(timespec="seconds"),
        "planted_by_id": person["id"],
        "planted_by_name": person["name"],
        "planting_reason": reason,
    }


def ensure_trees(world):
    scenery = world.setdefault("scenery_trees", [])
    known = {tree["id"] for tree in scenery}
    positions = [
        (f"tree:scenery:{x}:{y}", "Town tree", x, y) for x, y in SCENERY_POSITIONS
    ]
    for place in world.get("places", []):
        if place.get("kind") != "home":
            continue
        offsets = (
            [(-123, -67), (123, -63), (-126, 130), (135, 133)]
            if place.get("house_style") == "mansion"
            else [(-43, 17)]
            if place.get("driveway")
            else []
        )
        for index, (x, y) in enumerate(offsets):
            positions.append(
                (
                    f"tree:{place['id']}:{index}",
                    f"Tree at {place['name']}",
                    place["position"]["x"] + x,
                    place["position"]["y"] + y,
                )
            )
    for tree_id, name, x, y in positions:
        if tree_id not in known:
            scenery.append(
                {
                    "id": tree_id,
                    "kind": "tree",
                    "name": name,
                    "position": {"x": x, "y": y},
                    "planted_at": None,
                    "planted_by_id": None,
                    "planted_by_name": None,
                    "planting_reason": "existing_landscape",
                }
            )
    people = {person["id"]: person for person in world.get("people", [])}
    projects = {}
    for key, reason in (
        ("volunteering_projects", "volunteering"),
        ("municipal_projects", "town_employee"),
    ):
        for project in world.get(key, []):
            if (
                project.get("kind", "tree_planting") == "tree_planting"
                and project.get("status") == "completed"
            ):
                projects[project["id"]] = (project, reason)
    for tree in world.get("planted_trees", []):
        tree.setdefault("kind", "tree")
        tree.setdefault("name", "Town tree")
        project, reason = projects.get(tree["id"], ({}, None))
        person_id = project.get("person_id")
        tree.setdefault("planted_at", project.get("completed_at"))
        tree.setdefault("planted_by_id", person_id)
        tree.setdefault("planted_by_name", people.get(person_id, {}).get("name"))
        tree.setdefault("planting_reason", reason)
