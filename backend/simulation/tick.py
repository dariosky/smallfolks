from datetime import datetime, timedelta
from math import atan2, ceil, degrees, hypot

from simulation.economy import (
    BUSINESS_HOURS,
    can_pay,
    charge_daily_overhead,
    consider_takeovers,
    ensure_economy,
    pay_owner_dividends,
    pay_work_seconds,
    price_cents,
    purchase,
    record_regional_sales,
    reset_daily_sales,
)
from simulation.housing import home_parking_point
from simulation.mansions import inside_mansion
from simulation.prosperity import (
    CAR_PRICE,
    SPORTS_CAR_PRICE,
    assign_construction,
    buy_car,
    car_purchase_available,
    collect_loan_payments,
    consider_prosperity,
    ensure_prosperity,
    purchase_affordable,
    refresh_aspiration,
    work_on_expansion,
    workshop_parking,
)
from simulation.routing import (
    parking_point,
    pedestrian_route,
    position_on_route,
    road_edge_ids,
    road_route,
    route_length,
)

WALKING_SPEED = 18
DRIVING_SPEED = 90
TRAIN_SPEED = 120
RAIL_TOP = 640
RAIL_SIDE = 542
RAIL_CURVE = hypot(30, 30)
RAIL_POINTS = [
    {"x": x, "y": y} for x, y in [
        (450, 58), (1090, 58), (1120, 88), (1120, 630), (1090, 660),
        (450, 660), (420, 690), (420, 740), (390, 770), (70, 770),
        (40, 740), (40, 390), (70, 360), (390, 360), (420, 330),
        (420, 88), (450, 58),
    ]
]
RAIL_LENGTH = route_length(RAIL_POINTS)
STATIONS = {
    "market": {
        "id": "station:market",
        "name": "Market Square",
        "distance": 60,
        "position": {"x": 510, "y": 58},
        "platform": {"x": -120, "y": -9, "width": 160, "height": 18},
    },
    "eastgate": {
        "id": "station:eastgate",
        "name": "Eastgate",
        "distance": RAIL_TOP + RAIL_CURVE + 172,
        "position": {"x": 1120, "y": 260},
        "platform": {"x": -9, "y": -120, "width": 18, "height": 160},
    },
    "rowan": {
        "id": "station:rowan",
        "name": "Rowan Halt",
        "distance": RAIL_TOP + RAIL_CURVE + RAIL_SIDE + RAIL_CURVE + 440,
        "position": {"x": 650, "y": 660},
        "platform": {"x": -40, "y": -9, "width": 160, "height": 18},
    },
}
NEXT_STATION = {
    "station:market": "eastgate",
    "station:eastgate": "rowan",
    "station:rowan": "market",
}
TRAIN_CAPACITY = 8
TRAIN_CAR_CAPACITY = 4
SERVICE_CYCLE_MINUTES = 45
SERVICE_START_MINUTE = 6 * 60
SERVICE_END_MINUTE = 24 * 60
LAST_CYCLE_START_MINUTE = SERVICE_START_MINUTE + (
    (SERVICE_END_MINUTE - SERVICE_START_MINUTE) // SERVICE_CYCLE_MINUTES
) * SERVICE_CYCLE_MINUTES
BOARDING_SECONDS_PER_PERSON = 15
SERVICE_DEPARTURES = {"station:market": 3, "station:eastgate": 16, "station:rowan": 31}
SERVICE_TRAVEL_MINUTES = {
    ("station:market", "station:eastgate"): 10,
    ("station:market", "station:rowan"): 25,
    ("station:eastgate", "station:rowan"): 12,
    ("station:eastgate", "station:market"): 29,
    ("station:rowan", "station:market"): 14,
    ("station:rowan", "station:eastgate"): 27,
}
GROCERY_RESTOCK_DAYS = 3
GROCERY_BASE_BROWSING_MINUTES = 8
SOCIALIZING_MINUTES = 50
SOCIAL_BOREDOM_THRESHOLD = 30
CINEMA_VISIT_MINUTES = 70
CINEMA_BOREDOM_THRESHOLD = 28
HOME_MEAL_HUNGER_THRESHOLD = 55
MEAL_WINDOW_HUNGER_THRESHOLD = 35
HOME_ACTIVITY_MINUTES = 15
SLEEP_REST_THRESHOLD = 60
BEDTIME_START_MINUTE = 22 * 60
WAKE_TIME_MINUTE = 6 * 60
SOCIAL_NEED_THRESHOLD = 60
ENTERTAINMENT_BOREDOM_THRESHOLD = 45
PET_WALK_WARNING_SECONDS = 10 * 60 * 60
PET_WALK_DURATION_SECONDS = 20 * 60
PET_CLEANUP_DURATION_SECONDS = 20 * 60
LOGICAL_TICK_SECONDS = 15
NEED_PERIOD_SECONDS = {"hunger": 12 * 60, "rest": 20 * 60, "social": 30 * 60}
MINIMUM_STAFF = {"shop": 1, "bakery": 1, "bar": 1, "workplace": 1}


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


def _is_business_open_and_staffed(world: dict, place: dict, current_minutes: int) -> bool:
    if place.get("business", {}).get("status") == "bankrupt":
        return False
    opening, closing = BUSINESS_HOURS.get(place["id"], (0, 24 * 60))
    if not opening <= current_minutes < closing:
        return False
    minimum_staff = MINIMUM_STAFF.get(place["kind"], 0)
    working_staff = sum(
        person["workplace_id"] == place["id"]
        and person.get("shift_start_minute", 8 * 60)
        <= current_minutes
        < person.get("shift_end_minute", 17 * 60)
        and person.get("activity", "").startswith("Working as")
        for person in world["people"]
    )
    return working_staff >= minimum_staff


def _is_meal_time(current_minutes: int) -> bool:
    return 12 * 60 <= current_minutes < 13 * 60 or 19 * 60 <= current_minutes < 20 * 60


def _is_bedtime(current_minutes: int) -> bool:
    return current_minutes >= BEDTIME_START_MINUTE or current_minutes < WAKE_TIME_MINUTE


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


def _eat_lunch_at_work(person: dict, work: dict, now: datetime) -> None:
    minute_key = now.strftime("%Y-%m-%dT%H:%M")
    if now.minute % 5 == 0 and person.get("last_meal_minute") != minute_key:
        person["needs"]["hunger"] = max(0, person["needs"].get("hunger", 0) - 9)
        person["last_meal_minute"] = minute_key
    _move_to(
        person,
        work,
        "Eating lunch at work",
        "It is lunchtime and hunger is building, so this resident is taking a short meal break.",
        "Resume work after lunch",
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
        "They are sleeping at home to recover for the next day.",
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


def _wait_for_market(person: dict, home: dict, now: datetime) -> None:
    _move_to(
        person,
        home,
        "Waiting for Hearth Market to open",
        "Food is running low, but the market is closed or does not have enough staff to serve customers.",
        "Buy groceries when the market is open and staffed",
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
    ) < 55


def _at_place(person: dict, place: dict) -> bool:
    """A destination becomes usable only after its walk has completed."""
    return (
        person.get("target_place_id") == place["id"]
        and not person.get("direct_walk")
        and not person.get("route")
        and not person.get("on_train")
        and _is_near_place(person, place)
    )


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
        # Care takes over the person's route; an interrupted commute must be
        # replanned from wherever the owner finishes the pet task.
        person.pop("direct_walk", None)
        route = _residential_walk_route(world, person["position"], _position_at(person, destination))
        leg = {
            "owner_id": person["id"],
            "destination_id": destination["id"],
            "started_at_seconds": elapsed_seconds,
            "duration_seconds": max(2, ceil(route_length(route) / WALKING_SPEED)) * 60,
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
    person["journey"] = {
        "id": f"journey:{person['id']}:pet-care:{leg['started_at_seconds']}",
        "status": "active" if progress < 1 else "complete",
        "active_leg_index": 0,
        "legs": [{
            "id": f"leg:pet-care:{leg['started_at_seconds']}",
            "mode": "walk",
            "start_location": {"kind": "route", "edge_id": "pedestrian-route", "progress": 0},
            "end_location": {"kind": "place", "place_id": destination["id"]},
            "edge_ids": ["pedestrian-route"],
            "distance": route_length(leg["route"]),
            "progress": progress,
        }],
    }
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
        if not _at_place(person, home):
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
        if _at_place(person, home):
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
    """Station access uses a short local path, at the normal walking speed."""
    distance = hypot(
        destination["position"]["x"] - start["position"]["x"],
        destination["position"]["y"] - start["position"]["y"],
    )
    return max(1, ceil(distance / WALKING_SPEED))


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


def _residential_walk_route(world: dict, start: dict, destination: dict) -> list[dict]:
    if inside_mansion(world, start) or inside_mansion(world, destination):
        return road_route(world["roads"], start, destination)
    return pedestrian_route(start, destination)


def _walk_from_current_position(
    world: dict,
    person: dict,
    destination: dict,
    next_commitment: str,
    activity: str,
    explanation: str,
    local: bool = False,
    arrival_position: dict | None = None,
) -> bool:
    """Continue a route from the person's actual position; never snap to a timed phase."""
    elapsed_seconds = world["simulation"]["elapsed_seconds"]
    walk = person.get("direct_walk")
    if walk is None or walk.get("destination_id") != destination["id"]:
        origin = dict(person["position"])
        destination_position = arrival_position or _position_at(person, destination)
        route = (
            [origin, destination_position]
            if local
            else _residential_walk_route(world, origin, destination_position)
        )
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
    person["journey"] = {
        "id": f"journey:{person['id']}:{walk['started_at_seconds']}:{destination['id']}",
        "status": "active" if progress < 1 else "complete",
        "active_leg_index": 0,
        "legs": [{
            "id": f"leg:{walk['started_at_seconds']}:{destination['id']}",
            "mode": "walk",
            "start_location": {"kind": "route", "edge_id": "pedestrian-route", "progress": 0},
            "end_location": {"kind": "place", "place_id": destination["id"]},
            "edge_ids": ["station-access" if local else "pedestrian-route"],
            "distance": route_length(walk["route"]),
            "progress": progress,
        }],
    }
    if progress < 1:
        return False
    person["position"] = arrival_position or _position_at(person, destination)
    person.pop("route", None)
    person.pop("direct_walk", None)
    return True


def _car_journey(world: dict, person: dict, destination: dict, transport_required: bool = False) -> dict | None:
    """Choose the owner's reachable car only when the complete trip saves time."""
    start = {"position": person["position"]}
    walking_minutes = _walking_minutes(start, destination)
    direct_distance = hypot(
        person["position"]["x"] - destination["position"]["x"],
        person["position"]["y"] - destination["position"]["y"],
    )
    if not transport_required and (direct_distance < 350 or walking_minutes < 25):
        return None
    best = None
    for vehicle in world["vehicles"]:
        if (
            vehicle.get("owner_id") != person["id"]
            or vehicle.get("state") != "parked" or vehicle.get("reserved_by")
            or vehicle.get("driver_id")
        ):
            continue
        try:
            parked_at = (home_parking_point(world, destination, vehicle["id"])
                         if destination.get("driveway")
                         else parking_point(world["roads"], destination["position"]))
            if parked_at is None:
                continue
            if destination["id"] == "place:workshop":
                parked_at = workshop_parking(world, vehicle["id"])
                if parked_at is None:
                    continue
            route = road_route(world["roads"], vehicle["position"], parked_at)
        except ValueError:
            continue
        if any(
            other["id"] != vehicle["id"] and other.get("state") == "parked"
            and hypot(other["position"]["x"] - parked_at["x"], other["position"]["y"] - parked_at["y"]) < 25
            for other in world["vehicles"]
        ):
            continue
        access = max(2, ceil(hypot(
            person["position"]["x"] - vehicle["position"]["x"],
            person["position"]["y"] - vehicle["position"]["y"],
        ) / WALKING_SPEED))
        drive = max(2, ceil(route_length(route) / vehicle.get("speed_units_per_minute", DRIVING_SPEED)) + 1)
        arrival_position = _position_at(person, destination)
        egress = max(2, ceil(hypot(
            parked_at["x"] - arrival_position["x"],
            parked_at["y"] - arrival_position["y"],
        ) / WALKING_SPEED))
        total = access + drive + egress
        candidate = {
            "vehicle_id": vehicle["id"], "destination_id": destination["id"],
            "parking_position": parked_at, "road_route": route,
            "drive_seconds": drive * 60, "minutes": total,
        }
        if (transport_required or total + 5 < walking_minutes) and (best is None or total < best["minutes"]):
            best = candidate
    return best


def _run_car_trip(world: dict, person: dict) -> None:
    trip = person["car_trip"]
    vehicle = next(item for item in world["vehicles"] if item["id"] == trip["vehicle_id"])
    destination = _place(world, trip["destination_id"])
    elapsed = world["simulation"]["elapsed_seconds"]
    next_commitment = f"Reach {destination['name']}"
    if trip["phase"] == "access":
        if not _walk_from_current_position(
            world, person,
            {"id": vehicle["id"], "position": vehicle["position"]},
            next_commitment, f"Walking to {vehicle['name']}",
            "This car is reserved for the longer trip; the resident must reach its parking place first.",
            local=True,
            arrival_position=vehicle["position"],
        ):
            return
        trip["phase"] = "driving"
        trip["started_at_seconds"] = elapsed
        vehicle["driver_id"] = person["id"]
        vehicle["state"] = "driving"
    if trip["phase"] == "driving":
        progress = min(1, (elapsed - trip["started_at_seconds"]) / trip["drive_seconds"])
        position = position_on_route(trip["road_route"], progress)
        other = position_on_route(
            trip["road_route"], min(1, progress + 0.01) if progress < 1 else max(0, progress - 0.01)
        )
        dx = other["x"] - position["x"] if progress < 1 else position["x"] - other["x"]
        dy = other["y"] - position["y"] if progress < 1 else position["y"] - other["y"]
        if dx or dy:
            vehicle["heading"] = round(degrees(atan2(dy, dx)))
        vehicle["position"] = position
        vehicle["explanation"] = f"{person['name']} is driving on town roads toward {destination['name']}."
        person["position"] = dict(position)
        person["in_vehicle_id"] = vehicle["id"]
        person["target_place_id"] = destination["id"]
        person["activity"] = f"Driving {vehicle['name']} to {destination['name']}"
        person["explanation"] = "The car follows connected town roads to parking near the destination."
        person["next_commitment"] = next_commitment
        person["route"] = trip["road_route"]
        person["journey"] = {
            "id": f"journey:{person['id']}:car:{trip['started_at_seconds']}",
            "status": "active", "active_leg_index": 0,
            "legs": [{
                "id": f"leg:car:{vehicle['id']}", "mode": "car",
                "start_location": {"kind": "vehicle", "vehicle_id": vehicle["id"]},
                "end_location": {"kind": "place", "place_id": destination["id"]},
                "edge_ids": road_edge_ids(world["roads"], trip["road_route"]),
                "distance": route_length(trip["road_route"]), "progress": progress,
            }],
        }
        if progress < 1:
            return
        vehicle["position"] = dict(trip["parking_position"])
        vehicle["state"] = "parked"
        vehicle["parking_place_id"] = destination["id"]
        if destination.get("driveway"):
            vehicle["heading"] = 90
        vehicle["explanation"] = f"Parked near {destination['name']} and available to its owner."
        vehicle.pop("driver_id", None)
        vehicle.pop("reserved_by", None)
        person.pop("in_vehicle_id", None)
        person.pop("route", None)
        person.pop("direct_walk", None)
        trip["phase"] = "egress"
    if _walk_from_current_position(
        world, person, destination, next_commitment,
        f"Walking from parking to {destination['name']}",
        "The car is parked; the resident is walking the final leg from its actual position.",
        local=True,
    ):
        person.pop("car_trip", None)


def _start_car_trip(world: dict, person: dict, journey: dict) -> None:
    vehicle = next(item for item in world["vehicles"] if item["id"] == journey["vehicle_id"])
    vehicle["reserved_by"] = person["id"]
    vehicle["explanation"] = f"Reserved for {person['name']}, who is walking to its parking place."
    person.pop("direct_walk", None)
    person["car_trip"] = {**journey, "phase": "access"}
    _run_car_trip(world, person)


def _rail_distance(start: dict, destination: dict) -> float:
    return (destination["distance"] - start["distance"]) % RAIL_LENGTH


def _rail_position(distance: float) -> dict[str, int]:
    return position_on_route(RAIL_POINTS, (distance % RAIL_LENGTH) / RAIL_LENGTH)


def rail_track() -> list[dict]:
    """Use the same winding loop for simulation, stations, and coach rendering."""
    points = []
    distance = 0.0
    previous = None
    for point in RAIL_POINTS:
        if previous:
            distance += hypot(point["x"] - previous["x"], point["y"] - previous["y"])
        points.append({"distance": distance, **point})
        previous = point
    return points


def _rail_route(start: dict, destination: dict) -> list[dict[str, int]]:
    distance = _rail_distance(start, destination)
    steps = max(2, ceil(distance / 46))
    return [
        _rail_position(start["distance"] + distance * step / steps)
        for step in range(steps + 1)
    ]


def _service_state(minutes_since_start: int) -> dict:
    """Return the scheduled location, including the overnight Market Square layover."""
    minute_of_day = minutes_since_start
    market = STATIONS["market"]
    eastgate = STATIONS["eastgate"]
    rowan = STATIONS["rowan"]
    if minute_of_day < SERVICE_START_MINUTE or minute_of_day >= LAST_CYCLE_START_MINUTE:
        return {
            "distance": market["distance"],
            "at_station": market["id"],
            "service_state": "parked",
            "doors_open": False,
        }
    cycle_minute = (minute_of_day - SERVICE_START_MINUTE) % SERVICE_CYCLE_MINUTES
    def stop_state(station: dict, dwell_minute: float) -> dict:
        state = "stopped" if dwell_minute < 0.25 else (
            "departing" if dwell_minute >= 2.75 else "boarding"
        )
        return {
            "distance": station["distance"], "at_station": station["id"],
            "service_state": state, "doors_open": state == "boarding",
        }

    if cycle_minute < 3:
        return stop_state(market, cycle_minute)
    if cycle_minute < 13:
        progress = (cycle_minute - 3) / 10
        return {
            "distance": market["distance"]
            + _rail_distance(market, eastgate) * progress,
            "at_station": None,
            "service_state": "departing" if cycle_minute < 3.25 else (
                "approaching" if cycle_minute >= 12.75 else "travelling"
            ),
            "doors_open": False,
        }
    if cycle_minute < 16:
        return stop_state(eastgate, cycle_minute - 13)
    if cycle_minute < 28:
        progress = (cycle_minute - 16) / 12
        return {
            "distance": eastgate["distance"]
            + _rail_distance(eastgate, rowan) * progress,
            "at_station": None,
            "service_state": "departing" if cycle_minute < 16.25 else (
                "approaching" if cycle_minute >= 27.75 else "travelling"
            ),
            "doors_open": False,
        }
    if cycle_minute < 31:
        return stop_state(rowan, cycle_minute - 28)
    progress = (cycle_minute - 31) / 14
    return {
        "distance": rowan["distance"] + _rail_distance(rowan, market) * progress,
        "at_station": None,
        "service_state": "departing" if cycle_minute < 31.25 else (
            "approaching" if cycle_minute >= 44.75 else "travelling"
        ),
        "doors_open": False,
    }


def _next_service(
    departure: dict, arrival: dict, ready_at: datetime, boarding_buffer_seconds: int = 0
) -> tuple[datetime, datetime]:
    """Find the first reachable departure; no ride crosses the overnight layover."""
    travel = SERVICE_TRAVEL_MINUTES[(departure["id"], arrival["id"])]
    for day_offset in range(3):
        day = (ready_at + timedelta(days=day_offset)).date()
        midnight = datetime.combine(day, datetime.min.time())
        for cycle in range((LAST_CYCLE_START_MINUTE - SERVICE_START_MINUTE) // SERVICE_CYCLE_MINUTES):
            departure_minute = (
                SERVICE_START_MINUTE + cycle * SERVICE_CYCLE_MINUTES
                + SERVICE_DEPARTURES[departure["id"]]
            )
            if departure_minute + travel > LAST_CYCLE_START_MINUTE:
                continue
            departure_at = midnight + timedelta(minutes=departure_minute)
            if departure_at >= ready_at + timedelta(seconds=boarding_buffer_seconds):
                return departure_at, departure_at + timedelta(minutes=travel)
    raise ValueError("No Folk Loop service found within three days")


def _train_journey(start: dict, destination: dict, now: datetime | None = None) -> dict | None:
    """Choose the fastest useful complete trip, including access and timetable wait."""
    now = now or datetime.fromisoformat("2031-05-12T07:30:00")
    walking_minutes = _walking_minutes(start, destination)
    best: dict | None = None
    for departure in STATIONS.values():
        for arrival in STATIONS.values():
            if arrival["id"] == departure["id"]:
                continue
            access_minutes = _station_walk_minutes(start, departure)
            egress_minutes = _station_walk_minutes(arrival, destination)
            rail_minutes = SERVICE_TRAVEL_MINUTES[(departure["id"], arrival["id"])]
            departure_at, arrival_at = _next_service(
                departure, arrival, now + timedelta(minutes=access_minutes),
                boarding_buffer_seconds=45,
            )
            completed_at = arrival_at + timedelta(minutes=egress_minutes)
            total_minutes = (completed_at - now).total_seconds() / 60
            candidate = {
                "departure": departure,
                "arrival": arrival,
                "access_minutes": access_minutes,
                "rail_minutes": rail_minutes,
                "egress_minutes": egress_minutes,
                "minutes": total_minutes,
                "departure_at": departure_at.isoformat(timespec="seconds"),
                "arrival_at": arrival_at.isoformat(timespec="seconds"),
                "departure_minute": departure_at.hour * 60 + departure_at.minute,
                "arrival_minute": arrival_at.hour * 60 + arrival_at.minute,
            }
            if best is None or candidate["minutes"] < best["minutes"]:
                best = candidate
    if best and best["minutes"] + 4 < walking_minutes:
        return best
    return None


def _station_queue(world: dict, station_id: str) -> dict:
    queues = world.setdefault("station_queues", [])
    queue = next((item for item in queues if item["station_id"] == station_id), None)
    if queue is None:
        queue = {"station_id": station_id, "entries": []}
        queues.append(queue)
    return queue


def _remove_from_station_queues(world: dict, person_id: str) -> None:
    for queue in world.setdefault("station_queues", []):
        queue["entries"] = [
            entry for entry in queue["entries"] if entry["person_id"] != person_id
        ]


def _enqueue_train_trip(world: dict, person: dict, trip: dict) -> None:
    queue = _station_queue(world, trip["departure_id"])
    if not any(entry["person_id"] == person["id"] for entry in queue["entries"]):
        queue["entries"].append({
            "person_id": person["id"],
            "arrived_at_seconds": world["simulation"]["elapsed_seconds"],
            "tie_breaker": person["id"],
            "destination_station_id": trip["arrival_id"],
        })
        queue["entries"].sort(
            key=lambda entry: (entry["arrived_at_seconds"], entry["tie_breaker"])
        )
    trip["phase"] = "queued"
    person["train_departure_id"] = trip["departure_id"]
    person["train_arrival_id"] = trip["arrival_id"]


def _assign_train_seat(world: dict, person: dict) -> bool:
    """Assign the first empty seat without moving riders already aboard."""
    occupied = {
        (neighbour.get("train_car_index"), neighbour.get("train_seat_index"))
        for neighbour in world["people"] if neighbour.get("on_train")
    }
    for seat_number in range(TRAIN_CAPACITY):
        car_index, seat_index = divmod(seat_number, TRAIN_CAR_CAPACITY)
        if (car_index, seat_index) not in occupied:
            person["train_id"] = "train:folk-loop"
            person["train_car_index"] = car_index
            person["train_seat_index"] = seat_index
            person["train_car_id"] = f"carriage:folk-loop-{car_index + 1}"
            person["train_seat_id"] = f"seat:{car_index + 1}:{seat_index + 1}"
            person["on_train"] = True
            return True
    return False


def _alight(world: dict, person: dict, station: dict) -> None:
    trip = person.get("train_trip")
    person["position"] = _position_at(person, station)
    person["target_place_id"] = station["id"]
    person.pop("route", None)
    for key in (
        "on_train", "train_id", "train_car_index", "train_seat_index",
        "train_car_id", "train_seat_id", "train_departure_id", "train_arrival_id",
    ):
        person.pop(key, None)
    if trip is None:
        return
    if trip["arrival_id"] == station["id"]:
        trip["phase"] = "egress"
    else:
        # Every passenger leaves the train before its nightly layover.
        trip["departure_id"] = station["id"]
        _enqueue_train_trip(world, person, trip)


def _process_train_stop(world: dict, now: datetime, state: dict) -> None:
    station_id = state["at_station"]
    if station_id is None:
        return
    station = next(item for item in STATIONS.values() if item["id"] == station_id)
    for person in world["people"]:
        if person.get("on_train") and (state["doors_open"] or state["service_state"] == "parked") and (
            person.get("train_arrival_id") == station_id
            or state["service_state"] == "parked"
        ):
            _alight(world, person, station)
    if state["service_state"] == "departing":
        for entry in _station_queue(world, station_id)["entries"]:
            person = next(
                (item for item in world["people"] if item["id"] == entry["person_id"]), None
            )
            if person and person.get("train_trip", {}).get("phase") == "queued":
                person["train_trip"].setdefault(
                    "missed_service_at", now.isoformat(timespec="seconds")
                )
    if not state["doors_open"]:
        return
    minute_of_day = now.hour * 60 + now.minute + now.second / 60
    cycle_minute = (minute_of_day - SERVICE_START_MINUTE) % SERVICE_CYCLE_MINUTES
    stop_start = {"station:market": 0, "station:eastgate": 13, "station:rowan": 28}[station_id]
    slot = int((cycle_minute - stop_start) * 60 // BOARDING_SECONDS_PER_PERSON)
    if slot < 1 or slot >= 3 * 60 // BOARDING_SECONDS_PER_PERSON:
        return
    slot_key = f"{now.date()}:{int((minute_of_day - SERVICE_START_MINUTE) // SERVICE_CYCLE_MINUTES)}:{station_id}:{slot}"
    train = world["trains"][0]
    if train.get("last_boarding_slot") == slot_key:
        return
    train["last_boarding_slot"] = slot_key
    queue = _station_queue(world, station_id)
    departure_at = now + timedelta(
        seconds=(3 * 60 - (cycle_minute - stop_start) * 60)
    )
    for entry in list(queue["entries"]):
        person = next((item for item in world["people"] if item["id"] == entry["person_id"]), None)
        if person is None or person.get("train_trip", {}).get("phase") != "queued":
            queue["entries"].remove(entry)
            continue
        arrival = next(item for item in STATIONS.values() if item["id"] == entry["destination_station_id"])
        arrival_at = departure_at + timedelta(
            minutes=SERVICE_TRAVEL_MINUTES[(station_id, arrival["id"])]
        )
        service_end = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=1)
        if arrival_at > service_end:
            continue
        if not _assign_train_seat(world, person):
            break
        queue["entries"].remove(entry)
        trip = person["train_trip"]
        trip["phase"] = "aboard"
        trip.pop("missed_service_at", None)
        trip["boarded_departure_at"] = departure_at.isoformat(timespec="seconds")
        person["train_departure_id"] = station_id
        person["train_arrival_id"] = arrival["id"]
        person.pop("route", None)
        break


def _run_train_trip(world: dict, person: dict, now: datetime, state: dict) -> None:
    trip = person["train_trip"]
    departure = next(item for item in STATIONS.values() if item["id"] == trip["departure_id"])
    arrival = next(item for item in STATIONS.values() if item["id"] == trip["arrival_id"])
    destination = _place(world, trip["destination_id"])
    next_commitment = f"{person['role']} shift at {person.get('shift_start_minute', 480) // 60:02d}:00"
    if trip["phase"] == "access":
        if not _at_place(person, departure) and not _walk_from_current_position(
            world, person, departure, next_commitment,
            f"Walking to {departure['name']}",
            "Folk Loop is useful for this trip; the platform must be reached before boarding.",
            local=True,
        ):
            return
        _enqueue_train_trip(world, person, trip)
    if trip["phase"] == "queued":
        _enqueue_train_trip(world, person, trip)
        next_departure, next_arrival = _next_service(
            departure, arrival, now, boarding_buffer_seconds=45
        )
        queue = _station_queue(world, departure["id"])["entries"]
        rank = next(index for index, entry in enumerate(queue) if entry["person_id"] == person["id"])
        if (
            state["at_station"] == departure["id"]
            and state["doors_open"]
            and next_departure - now <= timedelta(minutes=3)
        ):
            free_seats = TRAIN_CAPACITY - sum(
                bool(neighbour.get("on_train")) for neighbour in world["people"]
            )
            if rank >= free_seats:
                next_departure, next_arrival = _next_service(
                    departure, arrival, next_departure + timedelta(seconds=1)
                )
        walking_arrival = now + timedelta(
            minutes=_walking_minutes({"position": person["position"]}, destination)
        )
        train_arrival = next_arrival + timedelta(
            minutes=_station_walk_minutes(arrival, destination)
        )
        if (
            trip.get("missed_service_at")
            and state["service_state"] != "parked"
            and walking_arrival + timedelta(minutes=4) < train_arrival
        ):
            _remove_from_station_queues(world, person["id"])
            person.pop("train_trip", None)
            person.pop("train_departure_id", None)
            person.pop("train_arrival_id", None)
            _walk_from_current_position(
                world, person, destination, next_commitment,
                f"Walking to {destination['name']}",
                f"The train was full or missed at {departure['name']}. Walking now reaches {destination['name']} by {walking_arrival:%H:%M}, before the next train's earliest {train_arrival:%H:%M} arrival.",
            )
            return
        if (
            state["service_state"] == "parked"
            and (next_departure - now).total_seconds() > 90 * 60
        ):
            _remove_from_station_queues(world, person["id"])
            person.pop("train_trip", None)
            person.pop("train_departure_id", None)
            person.pop("train_arrival_id", None)
            home = _place(world, person["home_place_id"])
            _walk_from_current_position(
                world, person, home, "Plan tomorrow's trip", "Walking home",
                "Folk Loop is parked from midnight to 06:00, so this resident is heading home and will plan again in the morning.",
            )
            return
        eta = train_arrival
        shift_minute = person.get("shift_start_minute", 8 * 60)
        shift_deadline = datetime.combine(
            eta.date(), datetime.min.time()
        ) + timedelta(minutes=shift_minute)
        lateness = (
            f" Expected work arrival {eta:%H:%M}, about {ceil((eta - shift_deadline).total_seconds() / 60)} minutes late."
            if eta > shift_deadline else f" Earliest work arrival {eta:%H:%M}."
        )
        person["position"] = _position_at(person, departure)
        person["target_place_id"] = departure["id"]
        person["activity"] = f"Queued for Folk Loop at {departure['name']}"
        person["explanation"] = (
            f"Folk Loop is parked overnight until 06:00. The next usable departure is "
            f"{next_departure:%H:%M}." + lateness
            if state["service_state"] == "parked"
            else f"This resident is {rank + 1} in the platform queue. The next scheduled departure is {next_departure:%H:%M}; boarding depends on available seats." + lateness
        )
        person["next_commitment"] = next_commitment
        person.pop("route", None)
        return
    if trip["phase"] == "aboard":
        person["position"] = _rail_position(state["distance"])
        person["target_place_id"] = arrival["id"]
        person["activity"] = f"Riding Folk Loop to {arrival['name']}"
        person["explanation"] = "This resident boarded at a station and keeps the same seat until their stop."
        person["next_commitment"] = next_commitment
        route = _rail_route(departure, arrival)
        person["route"] = route
        departure_at = datetime.fromisoformat(trip["boarded_departure_at"])
        ride_seconds = SERVICE_TRAVEL_MINUTES[(departure["id"], arrival["id"])] * 60
        progress = min(1, max(0, (now - departure_at).total_seconds() / ride_seconds))
        person["journey"] = {
            "id": f"journey:{person['id']}:{trip['boarded_departure_at']}",
            "status": "active", "active_leg_index": 0,
            "legs": [{
                "id": f"leg:{departure['id']}:{arrival['id']}", "mode": "train",
                "start_location": {"kind": "platform", "station_id": departure["id"]},
                "end_location": {"kind": "platform", "station_id": arrival["id"]},
                "edge_ids": ["rail:folk-loop"],
                "distance": _rail_distance(departure, arrival), "progress": progress,
            }],
        }
        return
    if _walk_from_current_position(
        world, person, destination, next_commitment,
        f"Walking from {arrival['name']} to {destination['name']}",
        "The train handled the long leg; this is the final local walk.",
        local=True,
    ):
        person.pop("train_trip", None)


def _restore_legacy_train_trip(person: dict) -> None:
    if person.get("train_trip"):
        return
    departure_id = person.get("train_departure_id")
    arrival_id = person.get("train_arrival_id")
    if departure_id not in {item["id"] for item in STATIONS.values()} or arrival_id not in {item["id"] for item in STATIONS.values()}:
        for key in (
            "on_train", "train_id", "train_car_index", "train_seat_index",
            "train_car_id", "train_seat_id", "train_departure_id", "train_arrival_id",
        ):
            person.pop(key, None)
        return
    if person.get("on_train"):
        car_index = person.get("train_car_index", 0)
        seat_index = person.get("train_seat_index", 0)
        person["train_id"] = "train:folk-loop"
        person["train_car_id"] = f"carriage:folk-loop-{car_index + 1}"
        person["train_seat_id"] = f"seat:{car_index + 1}:{seat_index + 1}"
    person["train_trip"] = {
        "departure_id": departure_id, "arrival_id": arrival_id,
        "destination_id": person["workplace_id"],
        "phase": "aboard" if person.get("on_train") else "access",
    }

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
    ensure_economy(world)
    ensure_prosperity(world)
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
    minute_of_day = now.hour * 60 + now.minute + now.second / 60
    train_state = _service_state(minute_of_day)
    world["trains"][0]["track"] = rail_track()
    world["trains"][0].setdefault("stations", [
        {key: value for key, value in station.items() if key != "distance"}
        for station in STATIONS.values()
    ])
    for person in world["people"]:
        _restore_legacy_train_trip(person)
        if person.get("train_trip", {}).get("phase") == "aboard":
            person["train_trip"].setdefault(
                "boarded_departure_at", now.isoformat(timespec="seconds")
            )
    _process_train_stop(world, now, train_state)
    _consume_daily_food(world, now)
    if seconds and now.date() != previous.date():
        reset_daily_sales(world, now)
        charge_daily_overhead(world, now)
        pay_owner_dividends(world, now)
        collect_loan_payments(world, now)
    if seconds and now.hour == 9 and now.minute == 0 and now.second == 0:
        consider_takeovers(world, now)
    if seconds:
        consider_prosperity(world, now)
        assign_construction(world)
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
        unemployed = work.get("business", {}).get("status") == "bankrupt"
        person["employment_status"] = "out of work" if unemployed else "employed"
        if unemployed:
            shift_start = shift_end = 0
        commute_minutes = _walking_minutes(home, work)
        commute_start = shift_start - commute_minutes
        if not person.get("train_trip") and not person.get("car_trip") and _care_for_pet(world, person, pippin, now):
            continue
        if person.get("car_trip"):
            _run_car_trip(world, person)
            continue
        if person.get("train_trip"):
            _run_train_trip(world, person, now, train_state)
            continue
        if person.get("vehicle_purchase") and 9 * 60 <= current_minutes < 20 * 60:
            model = person["vehicle_purchase"]["model"]
            cost = SPORTS_CAR_PRICE if model == "sports" else CAR_PRICE
            if (not car_purchase_available(world, person, model)
                    or household["food_servings"] < len(household["member_ids"])
                    or household["money_cents"] < 5_000
                    or not purchase_affordable(world, person, cost, now)):
                person.pop("vehicle_purchase", None)
                refresh_aspiration(world, person)
            else:
                shop = _place(world, "place:workshop")
                existing = next((v for v in world["vehicles"] if v["owner_id"] == person["id"]), None)
                if existing and existing.get("parking_place_id") != shop["id"]:
                    trip = _car_journey(world, person, shop, transport_required=True)
                    if trip:
                        _start_car_trip(world, person, trip)
                    continue
                if not _at_place(person, shop):
                    _walk_from_current_position(world, person, shop, "Buy a car at the workshop",
                                                "Walking to the workshop to buy a car",
                                                "This resident is visiting the workshop for their chosen car.")
                elif buy_car(world, person, home, now, model):
                    refresh_aspiration(world, person)
                    trip = _car_journey(world, person, home, transport_required=True)
                    if trip:
                        _start_car_trip(world, person, trip)
                else:
                    person["activity"] = "Waiting to buy a car at the workshop"
                    person["explanation"] = "Workshop parking must be available before the purchase can complete."
                continue
        project = next((project for project in world["construction_projects"]
                        if project["worker_id"] == person["id"] and project["status"] == "building"), None)
        if project and 9 * 60 <= current_minutes < 17 * 60:
            site = _place(world, project["home_place_id"])
            if not _at_place(person, site):
                _walk_from_current_position(
                    world, person, site, "Build the house upgrade", f"Walking to build at {site['name']}",
                    "A paid construction contract requires the carpenter to reach the house first.",
                )
            elif _is_meal_time(current_minutes) and person["needs"].get("hunger", 0) >= MEAL_WINDOW_HUNGER_THRESHOLD:
                _eat_lunch_at_work(person, site, now)
            else:
                _move_to(person, site, "Working on a house expansion", "This carpenter is completing a paid building contract.", "Finish the home and driveway")
                if seconds:
                    work_on_expansion(world, person, project, seconds, now)
            continue
        if _is_bedtime(current_minutes) and not shift_start <= current_minutes < shift_end:
            if _at_place(person, home):
                _sleep_at_home(person, home, now)
            else:
                _walk_from_current_position(
                    world, person, home, "Sleep at home", "Walking home to sleep",
                    "It is bedtime, so this resident is heading home to sleep.",
                )
            continue
        if commute_start <= current_minutes < shift_end and not _at_place(person, work) and shift_start == 8 * 60:
            train_journey = _train_journey({"position": person["position"]}, work, now)
            car_journey = _car_journey(world, person, work)
            if car_journey and (
                train_journey is None or car_journey["minutes"] + 3 < train_journey["minutes"]
            ):
                _start_car_trip(world, person, car_journey)
                continue
            if train_journey:
                person.pop("direct_walk", None)
                person["train_trip"] = {
                    "departure_id": train_journey["departure"]["id"],
                    "arrival_id": train_journey["arrival"]["id"],
                    "destination_id": work["id"],
                    "phase": "access",
                }
                _run_train_trip(world, person, now, train_state)
                continue
        if commute_start <= current_minutes < shift_start:
            if not _at_place(person, work):
                _walk_from_current_position(
                    world, person, work,
                    f"{person['role']} shift at {shift_start // 60:02d}:{shift_start % 60:02d}",
                    f"Walking to {work['name']}",
                    "The shift is approaching, so this resident is following the route to work.",
                )
        elif shift_start <= current_minutes < shift_end:
            if not _at_place(person, work):
                _walk_from_current_position(
                    world, person, work,
                    f"{person['role']} shift at {shift_start // 60:02d}:{shift_start % 60:02d}",
                    f"Walking to {work['name']}",
                    "The shift has started, but work begins only after this resident arrives.",
                )
                continue
            _increase_quiet_shift_boredom(world, person, work, now)
            if (
                _is_meal_time(current_minutes)
                and person["needs"].get("hunger", 0) >= MEAL_WINDOW_HUNGER_THRESHOLD
            ):
                _eat_lunch_at_work(person, work, now)
                continue
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
            if seconds:
                pay_work_seconds(world, person, seconds, now)
        else:
            if current_minutes < commute_start:
                if not _at_place(person, home):
                    _walk_from_current_position(
                        world, person, home, "Rest at home", "Walking home",
                        "There is no shift underway, so this resident is returning home.",
                    )
                elif person["needs"].get("rest", 0) >= SLEEP_REST_THRESHOLD:
                    _sleep_at_home(person, home, now)
                else:
                    _move_to(
                        person, home, "At home",
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
            market_available = _is_business_open_and_staffed(world, market, current_minutes)
            social_visit_today = person.get("social_visit_date") == now.date().isoformat()
            needs_social_outing = person["needs"].get("social", 0) >= SOCIAL_NEED_THRESHOLD
            wants_to_socialize = needs_social_outing or (
                person["needs"].get("boredom", 0) * person.get("social_inclination", 0.5)
                >= SOCIAL_BOREDOM_THRESHOLD
            )
            cinema_visit_today = person.get("cinema_visit_date") == now.date().isoformat()
            cinema_score = person["needs"].get("boredom", 0) * person.get("cinema_inclination", 0.4)
            social_score = person["needs"].get("boredom", 0) * person.get("social_inclination", 0.5)
            wants_cinema = (
                person["needs"].get("boredom", 0) >= ENTERTAINMENT_BOREDOM_THRESHOLD
                and cinema_score >= CINEMA_BOREDOM_THRESHOLD
            )
            chooses_cinema = (
                wants_cinema and not needs_social_outing and cinema_score > social_score
            )
            needs_sleep = person["needs"].get("rest", 0) >= SLEEP_REST_THRESHOLD
            needs_meal = (
                person["needs"].get("hunger", 0) >= HOME_MEAL_HUNGER_THRESHOLD
                or (
                    _is_meal_time(current_minutes)
                    and person["needs"].get("hunger", 0) >= MEAL_WINDOW_HUNGER_THRESHOLD
                )
            )
            plan = person.get("evening_plan")
            if plan and plan["date"] != now.date().isoformat():
                person.pop("evening_plan")
                plan = None
            if needs_meal and household["food_servings"] > 0 or needs_sleep:
                person.pop("evening_plan", None)
                if not _at_place(person, home):
                    car_journey = _car_journey(world, person, home)
                    if car_journey:
                        _start_car_trip(world, person, car_journey)
                        continue
                    _walk_from_current_position(
                        world, person, home, "Eat or rest at home", "Walking home",
                        "Food or rest takes priority, and this resident must reach home first.",
                    )
                elif needs_meal and household["food_servings"] > 0:
                    _eat_at_home(person, home, now)
                else:
                    _sleep_at_home(person, home, now)
                continue
            if plan is None:
                kind = None
                if (is_grocery_shopper and market_available
                    and can_pay(world, household["id"], household.get("grocery_servings_to_buy", 0) * price_cents(market))
                    and household.get("grocery_trip_date") != now.date().isoformat()):
                    kind = "grocery"
                elif (chooses_cinema and not cinema_visit_today and can_pay(world, person["id"], price_cents(cinema))
                      and _is_business_open_and_staffed(world, cinema, current_minutes)):
                    kind = "cinema"
                elif (wants_to_socialize and not social_visit_today and can_pay(world, person["id"], price_cents(bar))
                      and _is_business_open_and_staffed(world, bar, current_minutes)):
                    kind = "bar"
                if kind:
                    plan = {"date": now.date().isoformat(), "kind": kind, "phase": "travel"}
                    person["evening_plan"] = plan
            if plan:
                destination = {"grocery": market, "cinema": cinema, "bar": bar}[plan["kind"]]
                if plan["phase"] == "travel":
                    if not _at_place(person, destination):
                        car_journey = _car_journey(world, person, destination)
                        if car_journey:
                            _start_car_trip(world, person, car_journey)
                            continue
                        _walk_from_current_position(
                            world, person, destination, f"Visit {destination['name']}",
                            f"Walking to {destination['name']}",
                            "This resident is following the saved route from their current position.",
                        )
                        continue
                    plan["phase"] = "activity"
                    plan["started_at_seconds"] = simulation["elapsed_seconds"]
                    payer = household["id"] if plan["kind"] == "grocery" else person["id"]
                    units = household.get("grocery_servings_to_buy", 0) if plan["kind"] == "grocery" else 1
                    if not purchase(world, payer, destination, units, plan["kind"], now):
                        plan["phase"] = "return"
                if plan["phase"] == "activity":
                    duration = {
                        "grocery": _grocery_browsing_minutes(household),
                        "cinema": CINEMA_VISIT_MINUTES,
                        "bar": SOCIALIZING_MINUTES,
                    }[plan["kind"]] * 60
                    if simulation["elapsed_seconds"] - plan["started_at_seconds"] < duration:
                        if plan["kind"] == "grocery":
                            _shop_for_groceries(person, household, market, current_minutes, now)
                        elif plan["kind"] == "cinema":
                            _watch_film(person, cinema, current_minutes, now)
                        else:
                            _socialize_at_bar(person, bar, current_minutes, now)
                        continue
                    plan["phase"] = "return"
            if not _at_place(person, home):
                car_journey = _car_journey(world, person, home)
                if car_journey:
                    _start_car_trip(world, person, car_journey)
                    continue
                _walk_from_current_position(
                    world, person, home, "Return home", "Walking home",
                    "The evening activity is over, so this resident is walking home.",
                )
            else:
                person.pop("evening_plan", None)
                person.pop("carrying_groceries", None)
                if needs_meal and household["food_servings"] <= 0 and not market_available:
                    _wait_for_market(person, home, now)
                else:
                    _enjoy_home_activity(person, home, household, now)
                    if unemployed:
                        person["activity"] = "Looking for work"
                        person["explanation"] = f"{work['name']} closed, so this resident has no paid shift and is considering what to do next."
                        person["next_commitment"] = "Find work or reopen the business"

    if seconds and now.minute == 0 and now.second == 0:
        record_regional_sales(world, now, _is_business_open_and_staffed)

    world["trains"][0]["state"] = {
        **train_state,
        "capacity": TRAIN_CAPACITY,
        "car_capacity": TRAIN_CAR_CAPACITY,
        "service_hours": {"starts_at": "06:00", "ends_at": "00:00"},
        "stations": [
            {
                "station_id": station["id"],
                "name": station["name"],
                "queue_length": len(_station_queue(world, station["id"])["entries"]),
                "next_arrival_at": (departure_at - timedelta(minutes=3)).isoformat(timespec="seconds"),
                "next_departure_at": departure_at.isoformat(timespec="seconds"),
            }
            for station in STATIONS.values()
            for departure_at, _ in [
                _next_service(
                    station,
                    STATIONS[NEXT_STATION[station["id"]]],
                    now,
                )
            ]
        ],
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
                "seats": [
                    {
                        "id": f"seat:{car_index + 1}:{seat_index + 1}",
                        "passenger_id": next(
                            (
                                person["id"] for person in world["people"]
                                if person.get("on_train")
                                and person.get("train_car_index") == car_index
                                and person.get("train_seat_index") == seat_index
                            ),
                            None,
                        ),
                    }
                    for seat_index in range(TRAIN_CAR_CAPACITY)
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
