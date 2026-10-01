"""Apply the library and clinic staffing revision to existing towns."""

ASSIGNMENTS = {
    "person:nora": (
        "place:library",
        {"Student"},
        "place:library",
        "Library assistant",
        "student",
    ),
    "person:emma": (
        "place:library",
        {"Library assistant"},
        "place:school",
        "Teaching assistant",
        "teacher",
    ),
    "person:ada": (
        "place:library",
        {"Librarian"},
        "place:post-office",
        "Postal clerk",
        "host",
    ),
    "person:isabel": ("place:clinic", {"Nurse"}, "place:clinic", "Doctor", "doctor"),
    "person:oscar": (
        "place:clinic",
        {"Nurse"},
        "place:workshop",
        "Mechanic",
        "mechanic",
    ),
}


def ensure_staffing(world: dict) -> None:
    if world.get("staffing_version", 0) >= 1:
        return
    places = {place["id"] for place in world["places"]}
    for person in world["people"]:
        assignment = ASSIGNMENTS.get(person["id"])
        if assignment is None:
            continue
        previous_work, previous_roles, workplace, role, visual = assignment
        if (
            person.get("workplace_id") != previous_work
            or person.get("role") not in previous_roles
            or workplace not in places
        ):
            continue
        person.update(workplace_id=workplace, role=role, visual=visual)
        person["next_commitment"] = f"Next {role.lower()} shift"
        if person.get("activity", "").startswith("Working as "):
            person.update(
                activity="Waiting to start new assignment",
                explanation=f"Reassigned as {role.lower()}; the next shift follows the new workplace assignment.",
            )
    world["staffing_version"] = 1
