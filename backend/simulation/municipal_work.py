"""Town handymen perform useful tasks during their paid public shifts."""

from math import hypot

from simulation.economy import pay_work_seconds
from simulation.volunteering import PLANTING_SECONDS, _library_end, empty_parcels

TASK_LABELS = {
    "park_cleanup": "cleaning the park",
    "social_visit": "visiting a resident for companionship",
    "library_help": "helping at the library",
    "tree_planting": "planting trees",
}
TASK_SECONDS = {
    "park_cleanup": 3600,
    "social_visit": 3600,
    "library_help": 3600,
    "tree_planting": PLANTING_SECONDS,
}


def is_handyman(person: dict) -> bool:
    return (
        person.get("role") == "Town handyman"
        and person.get("workplace_id") == "place:townhall"
    )


def _site(world: dict, project: dict) -> dict:
    return next(
        (p for p in world["places"] if p["id"] == project["site_id"]),
        {"id": project["site_id"], "position": project["position"]},
    )


def _available_recipient(world: dict, recipient: dict, at_place) -> bool:
    home = next(p for p in world["places"] if p["id"] == recipient["home_place_id"])
    return at_place(recipient, home) and not recipient.get("activity", "").startswith(
        "Sleeping"
    )


def _new_project(
    world: dict, person: dict, kind: str, site: dict, now, recipient=None
) -> dict:
    project = {
        "id": f"municipal:{len(world['municipal_projects']) + 1}",
        "person_id": person["id"],
        "kind": kind,
        "site_id": site["id"],
        "position": dict(site["position"]),
        "status": "active",
        "started_at": now.isoformat(timespec="seconds"),
        "worked_seconds": 0,
        "required_seconds": TASK_SECONDS[kind],
    }
    if recipient:
        project["recipient_id"] = recipient["id"]
    world["municipal_projects"].append(project)
    return project


def _choose_project(world: dict, person: dict, now, at_place) -> dict | None:
    projects = world["municipal_projects"]
    own = [
        p
        for p in projects
        if p["person_id"] == person["id"] and p["status"] == "active"
    ]
    busy_sites = {
        p["site_id"]
        for p in projects
        if p["person_id"] != person["id"] and p["status"] == "active"
    }
    busy_sites.update(
        p["parcel_id"]
        for p in world["volunteering_projects"]
        if p["status"] == "active"
    )
    cleanup = next((p for p in own if p["kind"] == "park_cleanup"), None)
    if cleanup:
        if _site(world, cleanup)["cleanliness"] < 90:
            return cleanup  # Finish the accepted session even after crossing 50%.
        cleanup["status"] = "cancelled"
    parks = [
        p
        for p in world["places"]
        if p["kind"] == "park" and p["cleanliness"] < 50 and p["id"] not in busy_sites
    ]
    if parks:
        return _new_project(
            world,
            person,
            "park_cleanup",
            min(
                parks,
                key=lambda p: (
                    p["cleanliness"],
                    hypot(
                        p["position"]["x"] - person["position"]["x"],
                        p["position"]["y"] - person["position"]["y"],
                    ),
                ),
            ),
            now,
        )
    day = now.date().isoformat()
    for project in own:
        if project["kind"] == "social_visit":
            recipient = next(
                p for p in world["people"] if p["id"] == project["recipient_id"]
            )
            if _available_recipient(world, recipient, at_place):
                return project
            project["status"] = "cancelled"
    busy_recipients = {
        p.get("recipient_id") for p in projects if p["status"] == "active"
    }
    recipients = [
        p
        for p in world["people"]
        if p["id"] != person["id"]
        and not is_handyman(p)
        and p["needs"].get("social", 0) >= 60
        and p.get("municipal_visit_date") != day
        and p["id"] not in busy_recipients
        and _available_recipient(world, p, at_place)
    ]
    if recipients:
        recipient = max(recipients, key=lambda p: p["needs"]["social"])
        home = next(p for p in world["places"] if p["id"] == recipient["home_place_id"])
        return _new_project(world, person, "social_visit", home, now, recipient)
    library = next((p for p in world["places"] if p["id"] == "place:library"), None)
    if library and _library_end(world, now):
        project = next((p for p in own if p["kind"] == "library_help"), None)
        if project:
            return project
        if (
            library.get("municipal_library_help_date") != day
            and library["id"] not in busy_sites
        ):
            return _new_project(world, person, "library_help", library, now)
    planting = next((p for p in own if p["kind"] == "tree_planting"), None)
    if planting:
        return planting
    occupied = {p["site_id"] for p in projects if p["kind"] == "tree_planting"}
    occupied.update(
        p["parcel_id"]
        for p in world["volunteering_projects"]
        if p.get("kind", "tree_planting") in {"tree_planting", "community_gardening"}
    )
    parcels = [p for p in empty_parcels(world) if p["id"] not in occupied]
    if parcels:
        parcel = min(
            parcels,
            key=lambda p: hypot(
                p["position"]["x"] - person["position"]["x"],
                p["position"]["y"] - person["position"]["y"],
            ),
        )
        return _new_project(world, person, "tree_planting", parcel, now)
    return None


def run_municipal_work(world, person, now, seconds, walk, at_place, eat, rest) -> None:
    """Walk from the current position; pay actual work once at the normal wage."""
    minutes = now.hour * 60 + now.minute
    if (
        now.weekday() not in person["work_days"]
        or not person["shift_start_minute"] <= minutes < person["shift_end_minute"]
    ):
        return
    project = (
        _choose_project(world, person, now, at_place)
        if seconds
        else next(
            (
                p
                for p in world["municipal_projects"]
                if p["person_id"] == person["id"] and p["status"] == "active"
            ),
            None,
        )
    )
    townhall = next(p for p in world["places"] if p["id"] == "place:townhall")
    site = _site(world, project) if project else townhall
    if person["needs"].get("rest", 0) >= 70:
        if not at_place(person, townhall):
            walk(
                world,
                person,
                townhall,
                "Rest before resuming town work",
                "Walking to Town Hall to rest",
                "Urgent rest interrupts the town assignment.",
            )
        else:
            rest(person, townhall, now)
            person["activity"] = "Resting at Town Hall"
            person["explanation"] = (
                "Urgent rest interrupts the town assignment; no wages are earned during the break."
            )
        return
    if not at_place(person, site):
        walk(
            world,
            person,
            site,
            f"Town work: {TASK_LABELS[project['kind']]}"
            if project
            else "Wait for town work",
            f"Walking to town work: {TASK_LABELS[project['kind']]}"
            if project
            else "Walking to Town Hall",
            "The handymen prioritize parks below 50%, social work, and then planting trees.",
        )
        return
    if person["needs"].get("hunger", 0) >= 65 or (
        12 * 60 <= minutes < 13 * 60 and person["needs"].get("hunger", 0) >= 35
    ):
        eat(person, site, now)
        if not 12 * 60 <= minutes < 13 * 60:
            person["explanation"] = (
                "Urgent hunger interrupts town work for a meal; no wages are earned during the break."
            )
        return
    if project is None:
        person.update(
            activity="Waiting for a town work assignment",
            explanation="No available park, social-work, or planting assignment needs attention.",
            next_commitment="Review town work needs",
        )
        return
    person["activity"] = f"Town work: {TASK_LABELS[project['kind']]}"
    person["explanation"] = (
        "Paid Town Hall work at €12/hour; only time working on site earns wages."
    )
    person["next_commitment"] = (
        f"Finish {TASK_LABELS[project['kind']]} ({project['worked_seconds'] // 60}/{project['required_seconds'] // 60} minutes)"
    )
    if not seconds:
        return
    worked = min(seconds, project["required_seconds"] - project["worked_seconds"])
    project["worked_seconds"] += worked
    pay_work_seconds(world, person, worked, now)
    if project["kind"] == "social_visit":
        recipient = next(
            p for p in world["people"] if p["id"] == project["recipient_id"]
        )
        relief_points = project["worked_seconds"] * 35 // project["required_seconds"]
        relief = max(0, relief_points - project.get("social_relief_points", 0))
        recipient["needs"]["social"] = max(
            0, recipient["needs"].get("social", 0) - relief
        )
        project["social_relief_points"] = relief_points
    if project["worked_seconds"] < project["required_seconds"]:
        return
    kind = project["kind"]
    project.update(status="completed", completed_at=now.isoformat(timespec="seconds"))
    if kind == "park_cleanup":
        site["cleanliness"] = min(100, site["cleanliness"] + 40)
        site["cleanup_sessions"] += 1
    elif kind == "social_visit":
        recipient = next(
            p for p in world["people"] if p["id"] == project["recipient_id"]
        )
        recipient["municipal_visit_date"] = now.date().isoformat()
    elif kind == "library_help":
        site["library_help_sessions"] += 1
        site["municipal_library_help_date"] = now.date().isoformat()
    else:
        world.setdefault("planted_trees", []).append(
            {"id": project["id"], "position": project["position"]}
        )
    world["events"].append(
        {
            "at": now.isoformat(timespec="minutes"),
            "summary": f"{person['name']} completed town work: {TASK_LABELS[kind]}.",
        }
    )
