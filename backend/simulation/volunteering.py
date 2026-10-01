"""Optional sponsored community tasks with saved progress and reserved pay."""

from hashlib import sha256
from math import ceil, hypot

from generation.validators import place_footprint
from simulation.community import eligible_adult, ensure_community, pay_shared
from simulation.economy import record_income, transfer
from simulation.routing import nearest_road_point

PLANTING_SECONDS = 4 * 60 * 60
PLANTING_WAGE_CENTS = 2_400


def empty_parcels(world: dict) -> list[dict]:
    """Find clear planting plots, including space around buildings and tracks."""
    parcels = []
    width = world.get("map_size", {}).get("width", 1200)
    height = world.get("map_size", {}).get("height", 1000)
    track = world.get("trains", [{}])[0].get("track", [])
    for y in range(100, height - 50, 80):
        for x in range(100, width - 50, 80):
            position = {"x": x, "y": y}
            if any(
                abs(x - p["position"]["x"]) < place_footprint(p)[0] / 2 + 45
                and abs(y - p["position"]["y"]) < place_footprint(p)[1] / 2 + 55
                for p in world["places"]
            ):
                continue
            road = nearest_road_point(world["roads"], position)
            if hypot(x - road["x"], y - road["y"]) < 35:
                continue
            if len(track) > 1:
                rail = nearest_road_point(
                    [{"points": [[p["x"], p["y"]] for p in track]}], position
                )
                if hypot(x - rail["x"], y - rail["y"]) < 45:
                    continue
            parcels.append({"id": f"parcel:{x}:{y}", "position": position})
    return parcels


TASKS = {
    "tree_planting": (
        "Tree planting",
        "planting trees",
        PLANTING_SECONDS,
        PLANTING_WAGE_CENTS,
    ),
    "park_cleanup": ("Park cleanup", "cleaning the park", 3600, 600),
    "community_gardening": ("Community gardening", "community gardening", 7200, 1200),
    "library_help": ("Library help", "helping at the library", 3600, 600),
}


def _fraction(value: str) -> float:
    return int.from_bytes(sha256(value.encode()).digest()[:4], "big") / 2**32


def _library_end(world: dict, now) -> int:
    minutes = now.hour * 60 + now.minute
    return max(
        (
            p.get("shift_end_minute", 1020)
            for p in world["people"]
            if p.get("workplace_id") == "place:library"
            and now.weekday() in p["work_days"]
            and p.get("shift_start_minute", 480)
            <= minutes
            < p.get("shift_end_minute", 1020)
        ),
        default=0,
    )


def _candidates(world, person, now):
    projects = world["volunteering_projects"]
    occupied = {
        p["parcel_id"]
        for p in projects
        if p.get("kind", "tree_planting") in {"tree_planting", "community_gardening"}
        or p["status"] == "active"
    }
    occupied.update(
        p["site_id"]
        for p in world.get("municipal_projects", [])
        if p["kind"] == "tree_planting" or p["status"] == "active"
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
        nature = person["nature_inclination"]
        yield "tree_planting", parcel, nature + (0.1 if nature >= 0.65 else -0.1)
        yield "community_gardening", parcel, nature
    for place in world["places"]:
        if place["id"] in occupied:
            continue
        if place["kind"] == "park" and place["cleanliness"] < 90:
            yield "park_cleanup", place, person["community_inclination"]
        if place["id"] == "place:library" and _library_end(world, now):
            yield "library_help", place, person["library_inclination"]


def run_volunteering(
    world,
    person,
    now,
    seconds,
    free_until,
    unemployed,
    walk,
    at_place,
    travel_minutes=None,
):
    """Only site time counts; interruptions retain progress and escrow."""
    if not seconds:
        return False
    ensure_community(world)
    person.setdefault("nature_inclination", sum(map(ord, person["id"])) % 101 / 100)
    for preference in ("community", "library"):
        person.setdefault(
            f"{preference}_inclination", _fraction(f"{person['id']}:{preference}")
        )
    projects = world["volunteering_projects"]
    project = next(
        (
            p
            for p in projects
            if p["person_id"] == person["id"] and p["status"] == "active"
        ),
        None,
    )
    minutes = now.hour * 60 + now.minute + now.second / 60
    free_until = min(free_until, 18 * 60)
    if not 8 * 60 <= minutes < free_until:
        return False
    if person["needs"].get("hunger", 0) >= 65 or person["needs"].get("rest", 0) >= 70:
        return False
    if person.get("evening_plan") or person.get("restaurant_plan"):
        return False
    day = now.date().isoformat()
    if project is None:
        if free_until - minutes < 75:
            return False
        household = next(
            h for h in world["households"] if h["id"] == person["household_id"]
        )
        if not eligible_adult(person) or household["food_servings"] < len(
            household["member_ids"]
        ):
            return False
        if person.get("volunteering_date") == day:
            return False
        if not unemployed:
            motivated = (
                max(
                    person["nature_inclination"],
                    person["community_inclination"],
                    person["library_inclination"],
                )
                >= 0.5
            )
            if person["needs"].get("boredom", 0) < 20 and not motivated:
                return False
            choice = person.get("volunteering_choice", {})
            if choice.get("date") != day:
                choice = {
                    "date": day,
                    "accepted": _fraction(f"{person['id']}:{day}:volunteer") < 0.4,
                }
                person["volunteering_choice"] = choice
            if not choice["accepted"]:
                return False
        choices = []
        for kind, site, preference in _candidates(world, person, now):
            duration = TASKS[kind][2] / 60
            travel = (
                travel_minutes(person, site)
                if travel_minutes
                else max(
                    2,
                    ceil(
                        hypot(
                            site["position"]["x"] - person["position"]["x"],
                            site["position"]["y"] - person["position"]["y"],
                        )
                        / 18
                    ),
                )
            )
            end = (
                min(free_until, _library_end(world, now))
                if kind == "library_help"
                else free_until
            )
            home = next(
                p for p in world["places"] if p["id"] == person["home_place_id"]
            )
            return_travel = (
                travel_minutes({**person, "position": site["position"]}, home)
                if travel_minutes
                else max(
                    2,
                    ceil(
                        hypot(
                            site["position"]["x"] - home["position"]["x"],
                            site["position"]["y"] - home["position"]["y"],
                        )
                        / 18
                    ),
                )
            )
            if duration + travel + return_travel + 15 <= end - minutes:
                choices.append((preference, -travel, kind, site))
        if not choices:
            return False
        _, _, kind, site = max(choices, key=lambda c: (c[0], c[1], c[2]))
        label, _, required, wage = TASKS[kind]
        if not transfer(
            world,
            "treasury",
            "community_work",
            wage,
            "Reserve community-work payment",
            now,
        ):
            return False
        project = {
            "id": f"{kind}:{len(projects) + 1}",
            "kind": kind,
            "person_id": person["id"],
            "parcel_id": site["id"],
            "position": dict(site["position"]),
            "status": "active",
            "started_at": now.isoformat(timespec="seconds"),
            "worked_seconds": 0,
            "required_seconds": required,
            "wage_cents": wage,
            "payment_reserved": True,
        }
        projects.append(project)
        person["volunteering_date"] = day
    kind = project.get("kind", "tree_planting")
    label, activity, _, _ = TASKS[kind]
    if kind == "library_help" and not _library_end(world, now):
        return False
    site = next(
        (p for p in world["places"] if p["id"] == project["parcel_id"]),
        {"id": project["parcel_id"], "position": project["position"]},
    )
    if not at_place(person, site):
        walk(
            world,
            person,
            site,
            f"{label}: {project['required_seconds'] // 60} minutes of work",
            "Walking to a town hall tree-planting parcel"
            if kind == "tree_planting"
            else f"Walking to {label.lower()}",
            "Town Hall sponsors useful community work at €6/hour.",
        )
        return True
    person["activity"] = f"Volunteering: {activity}"
    person["explanation"] = (
        f"{label} for Town Hall; earns €{project['wage_cents'] / 100:g} on completion."
    )
    person["next_commitment"] = (
        f"Finish {label.lower()} ({project['worked_seconds'] // 60}/{project['required_seconds'] // 60} minutes), then return home"
    )
    project["worked_seconds"] = min(
        project["required_seconds"], project["worked_seconds"] + seconds
    )
    if project["worked_seconds"] < project["required_seconds"]:
        return True
    if not project.get("payment_reserved"):
        if not transfer(
            world,
            "treasury",
            "community_work",
            project["wage_cents"],
            "Reserve community-work payment",
            now,
        ):
            person["explanation"] = "Work is finished; waiting for Town Hall funding."
            return True
        project["payment_reserved"] = True
    wage = project["wage_cents"]
    if not pay_shared(
        world, person, wage, f"{label} wages", now, account="community_work"
    ):
        return True
    personal_share = (
        wage - wage * world["economy"]["household_contribution_percent"] // 100
    )
    record_income(person, personal_share, now)
    project.update(status="completed", completed_at=now.isoformat(timespec="seconds"))
    if kind == "tree_planting":
        world.setdefault("planted_trees", []).append(
            {"id": project["id"], "position": project["position"]}
        )
    elif kind == "community_gardening":
        world["community_gardens"].append(
            {"id": project["id"], "position": project["position"]}
        )
    elif kind == "park_cleanup":
        site["cleanliness"] = min(100, site["cleanliness"] + 40)
        site["cleanup_sessions"] += 1
    elif kind == "library_help":
        site["library_help_sessions"] += 1
    person["needs"]["boredom"] = max(0, person["needs"].get("boredom", 0) - 35)
    world["events"].append(
        {
            "at": now.isoformat(timespec="minutes"),
            "summary": f"{person['name']} completed {label.lower()} for Town Hall and earned €{wage / 100:g}.",
        }
    )
    return True
