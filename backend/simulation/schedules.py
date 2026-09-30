"""Weekly commitments and additive restaurant support for saved towns."""

from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256

RESTAURANT_ID = "place:restaurant"


def work_days(place: dict) -> list[int]:
    if place["id"] in {
        "place:clinic",
        "place:lantern-bar",
        "place:cinema",
        RESTAURANT_ID,
    }:
        return list(range(7))
    if place["kind"] in {"shop", "bakery"}:
        return list(range(6))
    return list(range(5))


def ensure_schedules(world: dict) -> None:
    if not any(place["id"] == RESTAURANT_ID for place in world["places"]):
        world["places"].append(
            {
                "id": RESTAURANT_ID,
                "name": "The Olive Table",
                "kind": "restaurant",
                "position": {"x": 700, "y": 720},
                "entrance": {"x": 700, "y": 768},
            }
        )
        world.setdefault("roads", []).append(
            {
                "id": "road:access-place:restaurant",
                "points": [[700, 920], [700, 754]],
            }
        )
    # Separate lunch and dinner staff keep ordinary residents free to dine out.
    for suffix, name, start, end in [
        ("lunch", "Sofia Marin", 11, 15),
        ("dinner", "Luca Marin", 18, 22),
    ]:
        person_id = f"person:restaurant-{suffix}"
        if any(person["id"] == person_id for person in world["people"]):
            continue
        template = world["people"][-1]
        person = {
            key: deepcopy(template[key])
            for key in (
                "kind",
                "home_place_id",
                "household_id",
                "palette",
                "needs",
                "social_inclination",
                "cinema_inclination",
            )
        }
        home = next(
            place for place in world["places"] if place["id"] == person["home_place_id"]
        )
        person.update(
            {
                "id": person_id,
                "name": name,
                "role": "Chef",
                "visual": "server",
                "workplace_id": RESTAURANT_ID,
                "shift_start_minute": start * 60,
                "shift_end_minute": end * 60,
                "position": dict(home["position"]),
                "target_place_id": home["id"],
                "activity": "At home",
                "money_cents": 5_000,
            }
        )
        world["people"].append(person)
        household = next(
            h for h in world["households"] if h["id"] == person["household_id"]
        )
        household["member_ids"].append(person_id)
        household["food_servings"] += 3
    places = {place["id"]: place for place in world["places"]}
    for person in world["people"]:
        person.setdefault("work_days", work_days(places[person["workplace_id"]]))
        # Stable preferences survive saves and do not depend on tick grouping.
        seed = int.from_bytes(sha256(person["id"].encode()).digest()[:4], "big")
        shift = person.get("shift_start_minute", 480)
        base = 480 if shift < 600 else 510 if shift < 840 else 540
        person.setdefault("preferred_wake_minute", base + seed % 7 * 15)
        person.setdefault("sleep_duration_minutes", 450 + (seed // 7) % 7 * 15)
        person.setdefault("morning_preparation_minutes", 30 + (seed // 49) % 4 * 15)
        person.setdefault("day_off_sleep_in_minutes", 45 + (seed // 196) % 6 * 15)
        person.setdefault(
            "restaurant_inclination", 0.35 + sum(map(ord, person["id"])) % 6 / 10
        )


def sleep_window(
    person: dict, workplace: dict, now: datetime, commute_minutes: int
) -> tuple[datetime, datetime]:
    """Current or next night's routine, allowing late shifts to cross midnight."""
    employed = workplace.get("business", {}).get("status") != "bankrupt"
    for offset in (0, 1, 2):
        morning = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=offset
        )
        working = employed and morning.weekday() in person["work_days"]
        wake_minute = person["preferred_wake_minute"]
        if working:
            wake_minute = min(
                wake_minute,
                person.get("shift_start_minute", 480)
                - commute_minutes
                - person["morning_preparation_minutes"],
            )
        else:
            wake_minute = max(480, wake_minute + person["day_off_sleep_in_minutes"])
        wake = morning + timedelta(minutes=wake_minute)
        bedtime = wake - timedelta(minutes=person["sleep_duration_minutes"])
        previous_day = morning - timedelta(days=1)
        if employed and previous_day.weekday() in person["work_days"]:
            home_after_work = previous_day + timedelta(
                minutes=person.get("shift_end_minute", 1020) + commute_minutes + 45
            )
            bedtime = max(bedtime, home_after_work)
        if now < wake:
            return bedtime, wake
    raise AssertionError("A future wake time must exist")
