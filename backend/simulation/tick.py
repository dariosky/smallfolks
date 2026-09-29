from datetime import datetime, timedelta
from math import ceil, cos, hypot, radians, sin

from simulation.routing import pedestrian_route, position_on_route, route_length

WALKING_SPEED = 18
TRAIN_SPEED = 120
RAIL_TOP = 640
RAIL_SIDE = 542
RAIL_CURVE = 47.1239
RAIL_LENGTH = RAIL_TOP * 2 + RAIL_SIDE * 2 + RAIL_CURVE * 4
STATIONS = {
    "market": {
        "id": "station:market",
        "name": "Market Square",
        "distance": 60,
        "position": {"x": 510, "y": 58},
    },
    "eastgate": {
        "id": "station:eastgate",
        "name": "Eastgate",
        "distance": RAIL_TOP + RAIL_CURVE + 172,
        "position": {"x": 1120, "y": 260},
    },
    "rowan": {
        "id": "station:rowan",
        "name": "Rowan Halt",
        "distance": RAIL_TOP + RAIL_CURVE + RAIL_SIDE + RAIL_CURVE + 440,
        "position": {"x": 650, "y": 660},
    },
}
TRAIN_CAPACITY = 8
TRAIN_CAR_CAPACITY = 4
SERVICE_CYCLE_MINUTES = 43
SERVICE_DEPARTURES = {"station:market": 3, "station:eastgate": 16, "station:rowan": 31}
SERVICE_TRAVEL_MINUTES = {
    ("station:market", "station:eastgate"): 10,
    ("station:market", "station:rowan"): 25,
    ("station:eastgate", "station:rowan"): 12,
    ("station:eastgate", "station:market"): 27,
    ("station:rowan", "station:market"): 12,
    ("station:rowan", "station:eastgate"): 25,
}
GROCERY_RESTOCK_DAYS = 3
GROCERY_BASE_BROWSING_MINUTES = 8
SOCIALIZING_MINUTES = 50
SOCIAL_BOREDOM_THRESHOLD = 30
CINEMA_VISIT_MINUTES = 70
CINEMA_BOREDOM_THRESHOLD = 28
HOME_MEAL_HUNGER_THRESHOLD = 55
HOME_ACTIVITY_MINUTES = 15
SLEEP_REST_THRESHOLD = 60
SOCIAL_NEED_THRESHOLD = 60
ENTERTAINMENT_BOREDOM_THRESHOLD = 45
PET_WALK_WARNING_SECONDS = 10 * 60 * 60
PET_WALK_DURATION_SECONDS = 20 * 60
PET_CLEANUP_DURATION_SECONDS = 20 * 60
LOGICAL_TICK_SECONDS = 15
NEED_PERIOD_SECONDS = {"hunger": 12 * 60, "rest": 20 * 60, "social": 30 * 60}


def _place(world: dict, place_id: str) -> dict:
    return next(place for place in world["places"] if place["id"] == place_id)


def _offset(person: dict) -> tuple[int, int]:
    number = sum(ord(character) for character in person["id"])
    return ((number % 5 - 2) * 11, ((number // 5) % 4 - 2) * 9)


def _position_at(person: dict, place: dict) -> dict[str, int]:
    offset_x, offset_y = _offset(person)
    return {
        "x": place["position"]["x"] + offset_x,
        "y": place["position"]["y"] + 31 + offset_y // 2,
    }


def _household(world: dict, person: dict) -> dict:
    return next(
        household
        for household in world["households"]
        if household["id"] == person["household_id"]
    )


def _household_food_days(household: dict) -> float:
    return household["food_servings"] / len(household["member_ids"])


def _household_needs_groceries(household: dict) -> bool:
    return household["food_servings"] <= len(household["member_ids"])


def _consume_daily_food(world: dict, now: datetime) -> None:
    """Each household consumes one serving per resident at dinner."""
    day = now.date().isoformat()
    if now.hour >= 19:
        for household in world["households"]:
            if household.get("last_food_consumption_date") != day:
                household["food_servings"] = max(
                    0, household["food_servings"] - len(household["member_ids"])
                )
                household["last_food_consumption_date"] = day


def _assign_grocery_shopper(household: dict, now: datetime) -> str:
    day = now.date().isoformat()
    if household.get("grocery_assigned_date") != day:
        member_ids = household["member_ids"]
        index = household.get("grocery_rotation_index", 0) % len(member_ids)
        household["grocery_shopper_id"] = member_ids[index]
        household["grocery_rotation_index"] = (index + 1) % len(member_ids)
        household["grocery_assigned_date"] = day
        household["grocery_servings_to_buy"] = max(
            0,
            len(member_ids) * GROCERY_RESTOCK_DAYS - household["food_servings"],
        )
    return household["grocery_shopper_id"]


def _grocery_browsing_minutes(household: dict) -> int:
    return GROCERY_BASE_BROWSING_MINUTES + household.get("grocery_servings_to_buy", 0)


def _shop_position(person: dict, market: dict, current_minutes: int) -> dict[str, int]:
    """Walk a small, deterministic aisle loop while shopping."""
    aisle_positions = [(-24, -13), (13, -15), (25, 9), (-9, 17), (-28, 5)]
    offset = sum(ord(character) for character in person["id"])
    aisle_x, aisle_y = aisle_positions[(current_minutes // 2 + offset) % len(aisle_positions)]
    return {
        "x": market["position"]["x"] + aisle_x,
        "y": market["position"]["y"] + aisle_y,
    }


def _shop_for_groceries(
    person: dict, household: dict, market: dict, current_minutes: int, now: datetime
) -> None:
    trip_day = now.date().isoformat()
    if household.get("grocery_trip_date") != trip_day:
        household["food_servings"] += household["grocery_servings_to_buy"]
        household["grocery_trip_date"] = trip_day
    person["carrying_groceries"] = True
    person["position"] = _shop_position(person, market, current_minutes)
    person["target_place_id"] = market["id"]
    person["activity"] = "Shopping at Hearth Market"
    person["explanation"] = (
        f"The household is buying {household['grocery_servings_to_buy']} servings for "
        f"{len(household['member_ids'])} people, so this visit takes proportionally longer."
    )
    person["next_commitment"] = "Return home with groceries"
    person.pop("route", None)


def _has_customers(world: dict, business: dict, worker: dict) -> bool:
    return any(
        person["id"] != worker["id"]
        and person.get("target_place_id") == business["id"]
        and person.get("activity", "").startswith("Shopping")
        for person in world["people"]
    )


def _increase_quiet_shift_boredom(world: dict, person: dict, workplace: dict, now: datetime) -> None:
    """Public-facing workers get restless during an empty quarter-hour."""
    if (
        workplace["kind"] in {"bakery", "shop"}
        and now.minute % 15 == 0
        and not _has_customers(world, workplace, person)
    ):
        person["needs"]["boredom"] = min(100, person["needs"].get("boredom", 20) + 2)


def _bar_position(person: dict, bar: dict, current_minutes: int) -> dict[str, int]:
    tables = [(-24, -10), (8, -16), (26, 5), (3, 18), (-23, 12)]
    offset = sum(ord(character) for character in person["id"])
    table_x, table_y = tables[(current_minutes // 3 + offset) % len(tables)]
    return {"x": bar["position"]["x"] + table_x, "y": bar["position"]["y"] + table_y}


def _socialize_at_bar(person: dict, bar: dict, current_minutes: int, now: datetime) -> None:
    person["social_visit_date"] = now.date().isoformat()
    person["position"] = _bar_position(person, bar, current_minutes)
    person["target_place_id"] = bar["id"]
    person["activity"] = "Socializing at The Lantern Bar"
    person["explanation"] = (
        "A quiet shift left this resident restless, and their social inclination made a relaxed bar visit appealing."
    )
    person["next_commitment"] = "Walk home after catching up"
    person.pop("route", None)
    if current_minutes % 5 == 0:
        person["needs"]["social"] = max(0, person["needs"]["social"] - 3)
        person["needs"]["boredom"] = max(0, person["needs"].get("boredom", 0) - 4)


def _cinema_position(person: dict, cinema: dict, current_minutes: int) -> dict[str, int]:
    seats = [(-26, -10), (-10, -10), (7, -10), (24, -10), (-18, 12), (0, 12), (18, 12)]
    offset = sum(ord(character) for character in person["id"])
    seat_x, seat_y = seats[(current_minutes // 8 + offset) % len(seats)]
    return {"x": cinema["position"]["x"] + seat_x, "y": cinema["position"]["y"] + seat_y}


def _watch_film(person: dict, cinema: dict, current_minutes: int, now: datetime) -> None:
    person["cinema_visit_date"] = now.date().isoformat()
    person["position"] = _cinema_position(person, cinema, current_minutes)
    person["target_place_id"] = cinema["id"]
    person["activity"] = "Watching a film at Clover Cinema"
    person["explanation"] = (
        "A film is a good evening change of scene for this resident's cinema inclination and boredom."
    )
    person["next_commitment"] = "Walk home after the film"
    person.pop("route", None)
    if current_minutes % 10 == 0:
        person["needs"]["boredom"] = max(0, person["needs"].get("boredom", 0) - 3)


def _eat_at_home(person: dict, home: dict, now: datetime) -> None:
    """A full hunger meter means a need to eat, so meals lower it over time."""
    minute_key = now.strftime("%Y-%m-%dT%H:%M")
    if now.minute % 5 == 0 and person.get("last_meal_minute") != minute_key:
        person["needs"]["hunger"] = max(0, person["needs"].get("hunger", 0) - 9)
        person["last_meal_minute"] = minute_key
    _move_to(
        person,
        home,
        "Cooking and eating at home",
        "Their hunger is high, so a proper meal takes priority before the rest of the evening.",
        "Relax at home after dinner",
    )


def _sleep_at_home(person: dict, home: dict, now: datetime) -> None:
    minute_key = now.strftime("%Y-%m-%dT%H:%M")
    if now.minute % 5 == 0 and person.get("last_sleep_minute") != minute_key:
        person["needs"]["rest"] = max(0, person["needs"].get("rest", 0) - 8)
        person["last_sleep_minute"] = minute_key
    _move_to(
        person,
        home,
        "Sleeping at home",
        "They are tired enough that rest takes priority over a social or entertaining evening.",
        "Wake up rested",
    )


def _enjoy_home_activity(person: dict, home: dict, household: dict, now: datetime) -> None:
    activities = [
        ("Reading at home", "A quiet book is a pleasant way to settle in after work.", "boredom", 3),
        ("Tending the garden", "A little garden time helps this resident unwind outdoors at home.", "boredom", 4),
        ("Calling a friend", "A low-key catch-up satisfies some social need without going back out.", "social", 4),
        ("Doing household chores", "A few shared household jobs keep the home comfortable.", "rest", -2),
        ("Practising a hobby", "Personal hobby time makes an otherwise quiet evening feel worthwhile.", "boredom", 5),
    ]
    slot = (now.hour * 60 + now.minute) // HOME_ACTIVITY_MINUTES
    activity, explanation, need, relief = activities[
        (sum(ord(character) for character in person["id"]) + slot) % len(activities)
    ]
    activity_key = f"{now.date().isoformat()}:{slot}"
    if person.get("last_home_activity_slot") != activity_key:
        person["needs"][need] = min(
            100, max(0, person["needs"].get(need, 0) - relief)
        )
        person["last_home_activity_slot"] = activity_key
    food_days = _household_food_days(household)
    _move_to(
        person,
        home,
        activity,
        f"{explanation} The household has food for about {food_days:g} more day(s).",
        f"{person['role']} shift tomorrow at {person.get('shift_start_minute', 480) // 60:02d}:00",
    )


def _pet_owner_ids(world: dict, pet: dict) -> list[str]:
    household = next(
        household for household in world["households"] if household["id"] == pet["household_id"]
    )
    return household["member_ids"]


def _ensure_pet_walk_contract(world: dict, pet: dict, now: datetime) -> None:
    """Add care fields to snapshots created before household pet care existed."""
    if "household_id" not in pet:
        guardian = next(person for person in world["people"] if person["id"] == pet["guardian_id"])
        pet["household_id"] = guardian["household_id"]
    pet.setdefault("max_walk_autonomy_seconds", 12 * 60 * 60)
    pet.setdefault("last_walk_at", (now - timedelta(hours=10)).isoformat(timespec="seconds"))
    pet.setdefault("walk_rotation_index", 0)
    pet.setdefault("needs", {}).setdefault("walk_out", 0)


def _update_pet_walk_need(pet: dict, now: datetime) -> None:
    if pet.get("walk_started_at_seconds") is not None:
        pet["walk_status"] = "out for a walk"
        return
    elapsed = max(0, (now - datetime.fromisoformat(pet["last_walk_at"])).total_seconds())
    maximum = pet["max_walk_autonomy_seconds"]
    pet["needs"]["walk_out"] = min(100, round(elapsed / maximum * 100))
    if pet.get("accident_cleaned"):
        pet["walk_status"] = "still needs a walk"
    elif elapsed > maximum:
        pet["accident_at_home"] = True
        pet["walk_status"] = "overdue — accident at home"
    elif elapsed >= PET_WALK_WARNING_SECONDS:
        pet["walk_status"] = "due soon"
    else:
        pet["walk_status"] = "comfortable"


def _assign_pet_owner(world: dict, pet: dict, key: str, now: datetime) -> str:
    day = now.date().isoformat()
    assignment_key = f"{key}_assigned_date"
    owner_key = f"{key}_owner_id"
    if pet.get(assignment_key) != day:
        owner_ids = _pet_owner_ids(world, pet)
        index = pet.get("walk_rotation_index", 0) % len(owner_ids)
        pet[owner_key] = owner_ids[index]
        pet["walk_rotation_index"] = (index + 1) % len(owner_ids)
        pet[assignment_key] = day
    return pet[owner_key]


def _is_near_place(person: dict, place: dict) -> bool:
    destination = _position_at(person, place)
    return hypot(
        person["position"]["x"] - destination["x"],
        person["position"]["y"] - destination["y"],
    ) < 35


def _walk_pet_care_leg(
    world: dict,
    person: dict,
    pet: dict,
    destination: dict,
    activity: str,
    explanation: str,
    next_commitment: str,
) -> bool:
    """Move the owner along a persisted care route, returning true on arrival."""
    elapsed_seconds = world["simulation"]["elapsed_seconds"]
    leg = pet.get("care_leg")
    if leg is None:
        route = pedestrian_route(person["position"], _position_at(person, destination))
        leg = {
            "owner_id": person["id"],
            "destination_id": destination["id"],
            "started_at_seconds": elapsed_seconds,
            "duration_seconds": _walking_minutes(
                {"position": person["position"]}, destination
            )
            * 60,
            "route": route,
        }
        pet["care_leg"] = leg
    progress = min(
        1,
        (elapsed_seconds - leg["started_at_seconds"]) / leg["duration_seconds"],
    )
    person["position"] = position_on_route(leg["route"], progress)
    person["target_place_id"] = destination["id"]
    person["activity"] = activity
    person["explanation"] = explanation
    person["next_commitment"] = next_commitment
    person["route"] = leg["route"]
    if progress < 1:
        return False
    person["position"] = _position_at(person, destination)
    person.pop("route", None)
    pet.pop("care_leg", None)
    return True


def _care_for_pet(world: dict, person: dict, pet: dict, now: datetime) -> bool:
    """Run a shared household walk or cleanup; return whether it owns this tick."""
    elapsed_seconds = world["simulation"]["elapsed_seconds"]
    home = _place(world, _household(world, person)["home_place_id"])
    park = _place(world, "place:park")
    if pet.get("accident_at_home"):
        cleaner = _assign_pet_owner(world, pet, "cleanup", now)
        if person["id"] != cleaner:
            return False
        if not _is_near_place(person, home):
            _walk_pet_care_leg(
                world,
                person,
                pet,
                home,
                "Heading home to clean after Pippin",
                "Pippin needs cleanup, so this owner is walking back to the household first.",
                "Clean up after Pippin",
            )
            return True
        started = pet.setdefault("cleanup_started_at_seconds", elapsed_seconds)
        if elapsed_seconds - started >= PET_CLEANUP_DURATION_SECONDS:
            pet.pop("accident_at_home", None)
            pet.pop("cleanup_started_at_seconds", None)
            pet["accident_cleaned"] = True
            pet["walk_status"] = "still needs a walk"
            _move_to(
                person,
                home,
                "Finished cleaning after Pippin",
                "Pippin's accident has been cleaned; a walk is still the next priority.",
                "Take Pippin out",
            )
        else:
            _move_to(
                person,
                home,
                "Cleaning after Pippin",
                "Pippin was left too long without a walk, so this household task takes priority.",
                "Take Pippin out",
            )
        return True
    if pet["walk_status"] not in {"due soon", "overdue — accident at home", "still needs a walk", "out for a walk"}:
        return False
    walker = _assign_pet_owner(world, pet, "walk", now)
    if person["id"] != walker:
        return False
    started = pet.setdefault("walk_started_at_seconds", elapsed_seconds)
    pet["walk_status"] = "out for a walk"
    phase = pet.setdefault("walk_phase", "to_home")
    if phase == "to_home":
        if _is_near_place(person, home):
            pet["walk_phase"] = "to_park"
        else:
            _walk_pet_care_leg(
                world,
                person,
                pet,
                home,
                "Heading home to walk Pippin",
                "Pippin needs a walk, so this owner is returning to the household first.",
                "Pick up Pippin at home",
            )
            return True
    if pet["walk_phase"] == "to_park":
        if not _walk_pet_care_leg(
            world,
            person,
            pet,
            park,
            "Walking Pippin",
            "Pippin is nearing the household's 12-hour autonomy limit, so an owner is taking them out early.",
            "Return home with Pippin",
        ):
            return True
        pet["walk_phase"] = "return_home"
        pet["last_walk_at"] = now.isoformat(timespec="seconds")
        pet["walk_status"] = "comfortable"
        pet["needs"]["walk_out"] = 0
    if pet["walk_phase"] == "return_home":
        if not _walk_pet_care_leg(
            world,
            person,
            pet,
            home,
            "Walking Pippin home",
            "Pippin has had the needed walk and is heading home with their owner.",
            "Return home with Pippin",
        ):
            return True
        pet["last_walk_at"] = now.isoformat(timespec="seconds")
        pet.pop("walk_started_at_seconds", None)
        pet.pop("walk_phase", None)
        pet.pop("accident_cleaned", None)
        pet["walk_status"] = "comfortable"
        pet["needs"]["walk_out"] = 0
        _move_to(
            person,
            home,
            "Back home after walking Pippin",
            "Pippin has had the needed walk and is comfortable again.",
            f"{person['role']} shift at {person.get('shift_start_minute', 480) // 60:02d}:00",
        )
    return True


def _walking_minutes(start: dict, destination: dict) -> int:
    route = pedestrian_route(start["position"], destination["position"])
    return max(2, ceil(route_length(route) / WALKING_SPEED))


def _station_walk_minutes(start: dict, destination: dict) -> int:
    """Short station access is measured on the local paths, not the road graph."""
    start_position = start["position"]
    destination_position = destination["position"]
    distance = hypot(
        destination_position["x"] - start_position["x"],
        destination_position["y"] - start_position["y"],
    )
    return max(1, ceil(distance / 25))


def _move_to(
    person: dict, place: dict, activity: str, explanation: str, next_commitment: str
) -> None:
    person["position"] = _position_at(person, place)
    person["target_place_id"] = place["id"]
    person["activity"] = activity
    person["explanation"] = explanation
    person["next_commitment"] = next_commitment
    person.pop("route", None)
    person.pop("journey", None)
    person.pop("direct_walk", None)
    person.pop("train_departure_id", None)
    person.pop("train_arrival_id", None)


def _walk_to(
    person: dict,
    start: dict,
    destination: dict,
    progress: float,
    next_commitment: str,
    activity: str | None = None,
    explanation: str | None = None,
) -> None:
    route = pedestrian_route(
        _position_at(person, start), _position_at(person, destination)
    )
    person["position"] = position_on_route(route, progress)
    person["target_place_id"] = destination["id"]
    person["activity"] = activity or f"Walking to {destination['name']}"
    person["explanation"] = explanation or (
        f"The {person['role'].lower()} shift starts at 08:00, so the reachable pedestrian route is underway."
    )
    person["next_commitment"] = next_commitment
    person["route"] = route
    person["journey"] = {
        "id": f"journey:{person['id']}:{start['id']}:{destination['id']}",
        "status": "active",
        "active_leg_index": 0,
        "legs": [
            {
                "id": f"leg:{start['id']}:{destination['id']}",
                "mode": "walk",
                "start_location": {"kind": "place", "place_id": start["id"]},
                "end_location": {"kind": "place", "place_id": destination["id"]},
                "edge_ids": ["pedestrian-route"],
                "distance": route_length(route),
                "progress": min(1, max(0, progress)),
            }
        ],
    }


def _walk_from_current_position(
    world: dict,
    person: dict,
    destination: dict,
    next_commitment: str,
    activity: str,
    explanation: str,
) -> bool:
    """Continue a route from the person's actual position; never snap to a timed phase."""
    elapsed_seconds = world["simulation"]["elapsed_seconds"]
    walk = person.get("direct_walk")
    if walk is None or walk.get("destination_id") != destination["id"]:
        route = pedestrian_route(person["position"], _position_at(person, destination))
        walk = {
            "destination_id": destination["id"],
            "started_at_seconds": elapsed_seconds,
            "duration_seconds": max(2, ceil(route_length(route) / WALKING_SPEED)) * 60,
            "route": route,
        }
        person["direct_walk"] = walk
    progress = min(1, (elapsed_seconds - walk["started_at_seconds"]) / walk["duration_seconds"])
    person["position"] = position_on_route(walk["route"], progress)
    person["target_place_id"] = destination["id"]
    person["activity"] = activity
    person["explanation"] = explanation
    person["next_commitment"] = next_commitment
    person["route"] = walk["route"]
    if progress < 1:
        return False
    person["position"] = _position_at(person, destination)
    person.pop("route", None)
    person.pop("direct_walk", None)
    return True


def _rail_distance(start: dict, destination: dict) -> float:
    return (destination["distance"] - start["distance"]) % RAIL_LENGTH


def _rail_position(distance: float) -> dict[str, int]:
    position = distance % RAIL_LENGTH
    if position <= RAIL_TOP:
        return {"x": round(450 + position), "y": 58}
    position -= RAIL_TOP
    if position <= RAIL_CURVE:
        angle = -90 + position / RAIL_CURVE * 90
        return {
            "x": round(1090 + 30 * cos(radians(angle))),
            "y": round(88 + 30 * sin(radians(angle))),
        }
    position -= RAIL_CURVE
    if position <= RAIL_SIDE:
        return {"x": 1120, "y": round(88 + position)}
    position -= RAIL_SIDE
    if position <= RAIL_CURVE:
        angle = position / RAIL_CURVE * 90
        return {
            "x": round(1090 + 30 * cos(radians(angle))),
            "y": round(630 + 30 * sin(radians(angle))),
        }
    position -= RAIL_CURVE
    if position <= RAIL_TOP:
        return {"x": round(1090 - position), "y": 660}
    position -= RAIL_TOP
    if position <= RAIL_CURVE:
        angle = 90 + position / RAIL_CURVE * 90
        return {
            "x": round(450 + 30 * cos(radians(angle))),
            "y": round(630 + 30 * sin(radians(angle))),
        }
    position -= RAIL_CURVE
    if position <= RAIL_SIDE:
        return {"x": 420, "y": round(630 - position)}
    position -= RAIL_SIDE
    angle = 180 + position / RAIL_CURVE * 90
    return {
        "x": round(450 + 30 * cos(radians(angle))),
        "y": round(88 + 30 * sin(radians(angle))),
    }


def _rail_route(start: dict, destination: dict) -> list[dict[str, int]]:
    distance = _rail_distance(start, destination)
    steps = max(2, ceil(distance / 46))
    return [
        _rail_position(start["distance"] + distance * step / steps)
        for step in range(steps + 1)
    ]


def _service_state(minutes_since_start: int) -> dict:
    """Return the clock-driven Folk Loop state; it never depends on passenger demand."""
    cycle_minute = minutes_since_start % SERVICE_CYCLE_MINUTES
    market = STATIONS["market"]
    eastgate = STATIONS["eastgate"]
    rowan = STATIONS["rowan"]
    if cycle_minute < 3:
        return {"distance": market["distance"], "at_station": market["id"]}
    if cycle_minute < 13:
        progress = (cycle_minute - 3) / 10
        return {
            "distance": market["distance"]
            + _rail_distance(market, eastgate) * progress,
            "at_station": None,
        }
    if cycle_minute < 16:
        return {"distance": eastgate["distance"], "at_station": eastgate["id"]}
    if cycle_minute < 28:
        progress = (cycle_minute - 16) / 12
        return {
            "distance": eastgate["distance"]
            + _rail_distance(eastgate, rowan) * progress,
            "at_station": None,
        }
    if cycle_minute < 31:
        return {"distance": rowan["distance"], "at_station": rowan["id"]}
    progress = (cycle_minute - 31) / 12
    return {
        "distance": rowan["distance"] + _rail_distance(rowan, market) * progress,
        "at_station": None,
    }


def _train_journey(start: dict, destination: dict) -> dict | None:
    walking_minutes = _walking_minutes(start, destination)
    best: dict | None = None
    for departure in STATIONS.values():
        for arrival in STATIONS.values():
            if arrival["id"] == departure["id"]:
                continue
            access_minutes = _station_walk_minutes(start, departure)
            egress_minutes = _station_walk_minutes(arrival, destination)
            rail_minutes = SERVICE_TRAVEL_MINUTES[(departure["id"], arrival["id"])]
            departure_minute = SERVICE_DEPARTURES[departure["id"]]
            arrival_minute = departure_minute + rail_minutes
            if arrival_minute + egress_minutes > 30:
                continue
            total_minutes = access_minutes + rail_minutes + egress_minutes
            candidate = {
                "departure": departure,
                "arrival": arrival,
                "access_minutes": access_minutes,
                "rail_minutes": rail_minutes,
                "egress_minutes": egress_minutes,
                "minutes": total_minutes,
                "departure_minute": departure_minute,
                "arrival_minute": arrival_minute,
            }
            if best is None or candidate["minutes"] < best["minutes"]:
                best = candidate
    if best and best["minutes"] + 4 < walking_minutes:
        return best
    return None


def _assign_train_seat(world: dict, person: dict) -> bool:
    """Give a boarding passenger one stable seat without repacking other riders."""
    occupied = {
        (neighbour.get("train_car_index"), neighbour.get("train_seat_index"))
        for neighbour in world["people"]
        if neighbour.get("on_train")
    }
    for seat_number in range(TRAIN_CAPACITY):
        seat = (seat_number // TRAIN_CAR_CAPACITY, seat_number % TRAIN_CAR_CAPACITY)
        if seat not in occupied:
            person["train_car_index"], person["train_seat_index"] = seat
            person["on_train"] = True
            return True
    return False


def _take_train_to(
    world: dict,
    person: dict,
    start: dict,
    destination: dict,
    journey: dict,
    minutes_since_start: int,
    next_commitment: str,
) -> None:
    departure = journey["departure"]
    arrival = journey["arrival"]
    access_minutes = journey["access_minutes"]
    departure_minute = journey["departure_minute"]
    arrival_minute = journey["arrival_minute"]
    journey_start = departure_minute - access_minutes
    if minutes_since_start < departure_minute:
        if minutes_since_start >= journey_start and minutes_since_start < 0:
            _walk_to(
                person,
                start,
                departure,
                (minutes_since_start - journey_start) / access_minutes,
                next_commitment,
                f"Walking to {departure['name']}",
                "The train makes this cross-town journey much faster than walking the whole way.",
            )
            return
        _move_to(
            person,
            departure,
            f"Queued for Folk Loop at {departure['name']}",
            "The scheduled Folk Loop service will board passengers when it reaches this platform.",
            next_commitment,
        )
        person["train_departure_id"] = departure["id"]
        person["train_arrival_id"] = arrival["id"]
    elif minutes_since_start < arrival_minute:
        if minutes_since_start == departure_minute and not person.get("on_train"):
            _assign_train_seat(world, person)
        if not person.get("on_train"):
            _move_to(
                person,
                departure,
                f"Queued for next Folk Loop at {departure['name']}",
                "All available seats were taken; this passenger remains safely on the platform.",
                next_commitment,
            )
            person["train_departure_id"] = departure["id"]
            person["train_arrival_id"] = arrival["id"]
            return
        route = _rail_route(departure, arrival)
        person["position"] = position_on_route(
            route, (minutes_since_start - departure_minute) / journey["rail_minutes"]
        )
        person["target_place_id"] = arrival["id"]
        person["activity"] = f"Riding Folk Loop to {arrival['name']}"
        person["explanation"] = (
            "The scheduled train is covering the long cross-town section while walking would take much longer."
        )
        person["next_commitment"] = next_commitment
        person["route"] = route
        person["journey"] = {
            "id": f"journey:{person['id']}:{departure['id']}:{arrival['id']}",
            "status": "active",
            "active_leg_index": 0,
            "legs": [
                {
                    "id": f"leg:{departure['id']}:{arrival['id']}",
                    "mode": "train",
                    "start_location": {"kind": "platform", "station_id": departure["id"]},
                    "end_location": {"kind": "platform", "station_id": arrival["id"]},
                    "edge_ids": ["rail:folk-loop"],
                    "distance": _rail_distance(departure, arrival),
                    "progress": min(
                        1,
                        max(0, (minutes_since_start - departure_minute) / journey["rail_minutes"]),
                    ),
                }
            ],
        }
        person["train_departure_id"] = departure["id"]
        person["train_arrival_id"] = arrival["id"]
    else:
        person.pop("on_train", None)
        person.pop("train_car_index", None)
        person.pop("train_seat_index", None)
        person.pop("train_departure_id", None)
        person.pop("train_arrival_id", None)
        _walk_to(
            person,
            arrival,
            destination,
            (minutes_since_start - arrival_minute) / journey["egress_minutes"],
            next_commitment,
            f"Walking from {arrival['name']} to {destination['name']}",
            "The train handled the long leg; this is the short final walk.",
        )


def _advance_needs(person: dict, seconds: int) -> None:
    accumulated = person.setdefault("need_elapsed_seconds", {})
    for need, period in NEED_PERIOD_SECONDS.items():
        elapsed = accumulated.get(need, 0) + seconds
        increase, accumulated[need] = divmod(elapsed, period)
        person["needs"][need] = min(100, person["needs"].get(need, 0) + increase)


def advance(world: dict, minutes: int) -> dict:
    """Advance in whole game minutes through the same fixed-second engine."""
    return advance_seconds(world, minutes * 60)


def advance_seconds(world: dict, seconds: int) -> dict:
    """Advance in fixed logical steps, independent of request grouping."""
    if seconds < 0:
        raise ValueError("Simulation time cannot move backwards")
    if seconds == 0:
        return _advance_step(world, 0)
    remaining = seconds
    while remaining:
        step = min(LOGICAL_TICK_SECONDS, remaining)
        _advance_step(world, step)
        remaining -= step
    return world


def _advance_step(world: dict, seconds: int) -> dict:
    previous = datetime.fromisoformat(world["clock"])
    now = previous + timedelta(seconds=seconds)
    world["clock"] = now.isoformat(timespec="seconds")
    simulation = world.setdefault(
        "simulation",
        {"elapsed_seconds": 0, "running": False, "speed": 1.0},
    )
    simulation["elapsed_seconds"] += seconds
    simulation["presentation_time_seconds"] = simulation["elapsed_seconds"]
    current_minutes = now.hour * 60 + now.minute
    minutes_since_service_start = (
        now.hour * 60 + now.minute + now.second / 60 - (7 * 60 + 30)
    )
    _consume_daily_food(world, now)
    pippin = world["pets"][0]
    _ensure_pet_walk_contract(world, pippin, now)
    _update_pet_walk_need(pippin, now)
    for person in world["people"]:
        _advance_needs(person, seconds)
        home = _place(world, person["home_place_id"])
        work = _place(world, person["workplace_id"])
        market = _place(world, "place:supermarket")
        bar = _place(world, "place:lantern-bar")
        cinema = _place(world, "place:cinema")
        household = _household(world, person)
        shift_start = person.get("shift_start_minute", 8 * 60)
        shift_end = person.get("shift_end_minute", 17 * 60)
        train_journey = _train_journey(home, work) if shift_start == 8 * 60 else None
        commute_minutes = _walking_minutes(home, work)
        commute_start = shift_start - commute_minutes
        if train_journey:
            commute_start = (
                7 * 60
                + 30
                + train_journey["departure_minute"]
                - train_journey["access_minutes"]
            )
        if _care_for_pet(world, person, pippin, now):
            continue
        if commute_start <= current_minutes < shift_start:
            elapsed_minutes = current_minutes - commute_start
            if train_journey:
                _take_train_to(
                    world,
                    person,
                    home,
                    work,
                    train_journey,
                    minutes_since_service_start,
                    f"{person['role']} shift at {shift_start // 60:02d}:{shift_start % 60:02d}",
                )
            else:
                _walk_to(
                    person,
                    home,
                    work,
                    elapsed_minutes / commute_minutes,
                    f"{person['role']} shift at {shift_start // 60:02d}:{shift_start % 60:02d}",
                )
        elif shift_start <= current_minutes < shift_end:
            _increase_quiet_shift_boredom(world, person, work, now)
            next_commitment = (
                "Buy groceries after work"
                if _household_needs_groceries(household)
                else "Return home after work"
            )
            _move_to(
                person,
                work,
                f"Working as {person['role'].lower()}",
                f"It is a scheduled {person['role'].lower()} shift, so this commitment takes priority.",
                next_commitment,
            )
        else:
            work_to_market_minutes = _walking_minutes(work, market)
            market_to_home_minutes = _walking_minutes(market, home)
            work_to_home_minutes = _walking_minutes(work, home)
            work_to_bar_minutes = _walking_minutes(work, bar)
            bar_to_home_minutes = _walking_minutes(bar, home)
            work_to_cinema_minutes = _walking_minutes(work, cinema)
            cinema_to_home_minutes = _walking_minutes(cinema, home)
            after_work_minutes = current_minutes - shift_end
            if after_work_minutes < 0:
                if person["needs"].get("rest", 0) >= SLEEP_REST_THRESHOLD:
                    _sleep_at_home(person, home, now)
                else:
                    _move_to(
                        person,
                        home,
                        "At home",
                        "There is no urgent commitment before work, so the household is staying home.",
                        f"{person['role']} shift at {shift_start // 60:02d}:{shift_start % 60:02d}",
                    )
                continue
            household_needs_groceries = _household_needs_groceries(household)
            grocery_shopper_id = (
                _assign_grocery_shopper(household, now)
                if household_needs_groceries
                else household.get("grocery_shopper_id")
            )
            is_grocery_shopper = (
                person["id"] == grocery_shopper_id
                and household.get("grocery_assigned_date") == now.date().isoformat()
            )
            grocery_browsing_minutes = _grocery_browsing_minutes(household)
            social_visit_today = person.get("social_visit_date") == now.date().isoformat()
            needs_social_outing = person["needs"].get("social", 0) >= SOCIAL_NEED_THRESHOLD
            wants_to_socialize = social_visit_today or needs_social_outing or (
                person["needs"].get("boredom", 0) * person.get("social_inclination", 0.5)
                >= SOCIAL_BOREDOM_THRESHOLD
            )
            cinema_visit_today = person.get("cinema_visit_date") == now.date().isoformat()
            cinema_score = person["needs"].get("boredom", 0) * person.get("cinema_inclination", 0.4)
            social_score = person["needs"].get("boredom", 0) * person.get("social_inclination", 0.5)
            wants_cinema = cinema_visit_today or (
                person["needs"].get("boredom", 0) >= ENTERTAINMENT_BOREDOM_THRESHOLD
                and cinema_score >= CINEMA_BOREDOM_THRESHOLD
            )
            chooses_cinema = cinema_visit_today or (
                wants_cinema and not needs_social_outing and cinema_score > social_score
            )
            needs_sleep = person["needs"].get("rest", 0) >= SLEEP_REST_THRESHOLD
            if needs_sleep and after_work_minutes < work_to_home_minutes:
                _walk_to(
                    person,
                    work,
                    home,
                    after_work_minutes / work_to_home_minutes,
                    "Sleep at home",
                    "Walking home to rest",
                    "They are tired enough that rest takes priority over the evening's other plans.",
                )
            elif needs_sleep:
                if _is_near_place(person, home):
                    _sleep_at_home(person, home, now)
                else:
                    _walk_from_current_position(
                        world,
                        person,
                        home,
                        "Sleep at home",
                        "Walking home to rest",
                        "They are tired enough that rest takes priority over the evening's other plans.",
                    )
            elif is_grocery_shopper and after_work_minutes < work_to_market_minutes:
                _walk_to(
                    person,
                    work,
                    market,
                    after_work_minutes / work_to_market_minutes,
                    "Buy groceries at Hearth Market",
                    "Walking to Hearth Market",
                    "Food at home is running low, so groceries take priority before going home.",
                )
            elif is_grocery_shopper and after_work_minutes < (
                work_to_market_minutes + grocery_browsing_minutes
            ):
                _shop_for_groceries(person, household, market, current_minutes, now)
            elif is_grocery_shopper and after_work_minutes < (
                work_to_market_minutes
                + grocery_browsing_minutes
                + market_to_home_minutes
            ):
                _walk_to(
                    person,
                    market,
                    home,
                    (after_work_minutes - work_to_market_minutes - grocery_browsing_minutes)
                    / market_to_home_minutes,
                    "Make dinner at home",
                    "Walking home with groceries",
                    "The pantry has been restocked; the next stop is home for dinner.",
                )
            elif chooses_cinema and after_work_minutes < work_to_cinema_minutes:
                _walk_to(
                    person,
                    work,
                    cinema,
                    after_work_minutes / work_to_cinema_minutes,
                    "Watch a film at Clover Cinema",
                    "Walking to Clover Cinema",
                    "A film suits this resident's cinema inclination after a tiring day.",
                )
            elif chooses_cinema and after_work_minutes < work_to_cinema_minutes + CINEMA_VISIT_MINUTES:
                if _is_near_place(person, cinema):
                    _watch_film(person, cinema, current_minutes, now)
                else:
                    _walk_from_current_position(
                        world,
                        person,
                        cinema,
                        "Watch a film at Clover Cinema",
                        "Walking to Clover Cinema",
                        "This resident wants entertainment, so they are walking to the cinema first.",
                    )
            elif chooses_cinema and after_work_minutes < (
                work_to_cinema_minutes + CINEMA_VISIT_MINUTES + cinema_to_home_minutes
            ):
                _walk_to(
                    person,
                    cinema,
                    home,
                    (after_work_minutes - work_to_cinema_minutes - CINEMA_VISIT_MINUTES)
                    / cinema_to_home_minutes,
                    "Make dinner at home",
                    "Walking home after the film",
                    "The film is over, and this resident is heading home.",
                )
            elif wants_to_socialize and after_work_minutes < work_to_bar_minutes:
                if _is_near_place(person, work):
                    _walk_to(
                        person,
                        work,
                        bar,
                        after_work_minutes / work_to_bar_minutes,
                        "Meet neighbours at The Lantern Bar",
                        "Walking to The Lantern Bar",
                        "A quiet shift was boring, and social time sounds more appealing than going straight home.",
                    )
                else:
                    _walk_from_current_position(
                        world,
                        person,
                        bar,
                        "Meet neighbours at The Lantern Bar",
                        "Walking to The Lantern Bar",
                        "Social time sounds appealing, but this resident still has to walk there.",
                    )
            elif wants_to_socialize and after_work_minutes < (
                work_to_bar_minutes + SOCIALIZING_MINUTES
            ):
                if _is_near_place(person, bar):
                    _socialize_at_bar(person, bar, current_minutes, now)
                else:
                    _walk_from_current_position(
                        world,
                        person,
                        bar,
                        "Meet neighbours at The Lantern Bar",
                        "Walking to The Lantern Bar",
                        "Social time sounds appealing, but this resident still has to walk there.",
                    )
            elif wants_to_socialize and after_work_minutes < (
                work_to_bar_minutes + SOCIALIZING_MINUTES + bar_to_home_minutes
            ):
                _walk_to(
                    person,
                    bar,
                    home,
                    (after_work_minutes - work_to_bar_minutes - SOCIALIZING_MINUTES)
                    / bar_to_home_minutes,
                    "Make dinner at home",
                    "Walking home after socializing",
                    "The bar visit is over; this resident feels less restless and is heading home.",
                )
            elif not is_grocery_shopper and after_work_minutes < work_to_home_minutes:
                _walk_to(
                    person,
                    work,
                    home,
                    after_work_minutes / work_to_home_minutes,
                    "Make dinner at home",
                    "Walking home after work",
                    "There is enough food at home for several days, so there is no need to shop today.",
                )
            else:
                person.pop("carrying_groceries", None)
                if not _is_near_place(person, home):
                    _walk_from_current_position(
                        world,
                        person,
                        home,
                        "Return home",
                        "Walking home",
                        "The evening activity is over, so this resident is walking home rather than appearing there.",
                    )
                elif person["needs"].get("hunger", 0) >= HOME_MEAL_HUNGER_THRESHOLD:
                    _eat_at_home(person, home, now)
                else:
                    _enjoy_home_activity(person, home, household, now)

    train_state = _service_state(minutes_since_service_start)
    world["trains"][0]["state"] = {
        **train_state,
        "capacity": TRAIN_CAPACITY,
        "car_capacity": TRAIN_CAR_CAPACITY,
        "passenger_ids": [
            person["id"] for person in world["people"] if person.get("on_train")
        ],
        "carriages": [
            {
                "id": f"carriage:folk-loop-{car_index + 1}",
                "passenger_ids": [
                    person["id"]
                    for person in world["people"]
                    if person.get("on_train") and person.get("train_car_index") == car_index
                ],
            }
            for car_index in range(TRAIN_CAPACITY // TRAIN_CAR_CAPACITY)
        ],
    }

    pippin_home = _place(
        world,
        next(
            household["home_place_id"]
            for household in world["households"]
            if household["id"] == pippin["household_id"]
        ),
    )
    if pippin.get("walk_started_at_seconds") is not None:
        walker_id = pippin.get("walk_owner_id")
        walker = next((person for person in world["people"] if person["id"] == walker_id), None)
        if pippin.get("walk_phase") == "to_home":
            pippin["position"] = {
                "x": pippin_home["position"]["x"] - 17,
                "y": pippin_home["position"]["y"] + 28,
            }
            pippin["activity"] = "Waiting for their walk"
            pippin["explanation"] = "An owner is walking home to pick Pippin up."
        else:
            pippin["position"] = dict(walker["position"] if walker else pippin_home["position"])
            pippin["activity"] = f"Walking with {walker['name'] if walker else 'an owner'}"
            pippin["explanation"] = "A household owner is taking Pippin out before the 12-hour limit."
    elif pippin.get("accident_at_home"):
        pippin["position"] = {
            "x": pippin_home["position"]["x"] - 17,
            "y": pippin_home["position"]["y"] + 28,
        }
        pippin["activity"] = "Needs cleanup at home"
        pippin["explanation"] = "Pippin went beyond the 12-hour walk limit; the household needs to clean up."
    else:
        pippin["position"] = {
            "x": pippin_home["position"]["x"] - 17,
            "y": pippin_home["position"]["y"] + 28,
        }
        pippin["activity"] = (
            "Waiting for a walk" if pippin["walk_status"] != "comfortable" else "Resting at home"
        )
        pippin["explanation"] = (
            "Pippin needs a household walk next."
            if pippin["walk_status"] != "comfortable"
            else "Pippin is safe at home and has plenty of walk autonomy remaining."
        )
    world["events"] = world["events"][-12:]
    return world
