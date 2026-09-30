"""Saved town-hall planting projects, chosen during residents' free time."""

from math import hypot

from generation.validators import place_footprint
from simulation.economy import can_pay, record_income, transfer
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


def run_volunteering(
    world, person, now, seconds, free_until, unemployed, walk, at_place
):
    """Pause for commitments/needs; credit only time actually spent on site."""
    person.setdefault("nature_inclination", sum(map(ord, person["id"])) % 101 / 100)
    projects = world.setdefault("volunteering_projects", [])
    project = next(
        (
            p
            for p in projects
            if p["person_id"] == person["id"] and p["status"] == "active"
        ),
        None,
    )
    minutes = now.hour * 60 + now.minute
    if not 8 * 60 <= minutes < 18 * 60:
        return False
    if person["needs"].get("hunger", 0) >= 65 or person["needs"].get("rest", 0) >= 70:
        return False
    if project is None:
        household = next(
            h for h in world["households"] if h["id"] == person["household_id"]
        )
        if household["food_servings"] < len(household["member_ids"]):
            return False
        if person.get("volunteering_date") == now.date().isoformat():
            return False
        if not unemployed and (
            person["nature_inclination"] < 0.65
            or person["needs"].get("boredom", 0) < 35
        ):
            return False
        if (
            free_until - minutes < 5 * 60
            or person.get("evening_plan")
            or person.get("restaurant_plan")
        ):
            return False
        reserved = sum(PLANTING_WAGE_CENTS for p in projects if p["status"] == "active")
        if not can_pay(world, "treasury", reserved + PLANTING_WAGE_CENTS):
            return False
        occupied = {p["parcel_id"] for p in projects}
        parcels = [p for p in empty_parcels(world) if p["id"] not in occupied]
        if not parcels:
            return False
        parcel = min(
            parcels,
            key=lambda p: hypot(
                p["position"]["x"] - person["position"]["x"],
                p["position"]["y"] - person["position"]["y"],
            ),
        )
        project = {
            "id": f"planting:{len(projects) + 1}",
            "person_id": person["id"],
            "parcel_id": parcel["id"],
            "position": parcel["position"],
            "status": "active",
            "started_at": now.isoformat(timespec="seconds"),
            "worked_seconds": 0,
            "required_seconds": PLANTING_SECONDS,
            "wage_cents": PLANTING_WAGE_CENTS,
        }
        projects.append(project)
        person["volunteering_date"] = now.date().isoformat()
    site = {"id": project["parcel_id"], "position": project["position"]}
    if not at_place(person, site):
        walk(
            world,
            person,
            site,
            "Plant trees for four hours",
            "Walking to a town hall tree-planting parcel",
            "Town Hall offers a small wage for useful work in nature.",
        )
        return True
    person["activity"] = "Volunteering: planting trees"
    person["explanation"] = (
        "Planting trees for Town Hall; four hours of work earns €24."
    )
    person["next_commitment"] = (
        f"Finish planting ({project['worked_seconds'] // 60}/240 minutes), then return home"
    )
    project["worked_seconds"] = min(
        PLANTING_SECONDS, project["worked_seconds"] + seconds
    )
    if project["worked_seconds"] < PLANTING_SECONDS:
        return True
    if not can_pay(world, "treasury", PLANTING_WAGE_CENTS):
        person["explanation"] = (
            "Planting is finished; waiting for Town Hall to pay the wage."
        )
        return True
    share = (
        PLANTING_WAGE_CENTS * world["economy"]["household_contribution_percent"] // 100
    )
    transfer(
        world,
        "treasury",
        person["household_id"],
        share,
        "Shared tree-planting wages",
        now,
    )
    transfer(
        world,
        "treasury",
        person["id"],
        PLANTING_WAGE_CENTS - share,
        "Tree-planting wages",
        now,
    )
    record_income(person, PLANTING_WAGE_CENTS - share, now)
    project.update(status="completed", completed_at=now.isoformat(timespec="seconds"))
    world.setdefault("planted_trees", []).append(
        {"id": project["id"], "position": project["position"]}
    )
    person["needs"]["boredom"] = max(0, person["needs"].get("boredom", 0) - 35)
    world["events"].append(
        {
            "at": now.isoformat(timespec="minutes"),
            "summary": f"{person['name']} planted trees for Town Hall and earned €24.",
        }
    )
    return True
