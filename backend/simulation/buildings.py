"""Persist the operating state used by building inspectors and animations."""

from datetime import datetime, timedelta

from simulation.economy import BUSINESS_HOURS
from simulation.schedules import work_days


def _windows(
    world: dict, place: dict, now: datetime
) -> list[tuple[datetime, datetime]]:
    opening, closing = BUSINESS_HOURS.get(place["id"], (0, 24 * 60))
    windows = []
    staff = [p for p in world["people"] if p["workplace_id"] == place["id"]]
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(-8, 9):
        day = midnight + timedelta(days=offset)
        for person in staff:
            if day.weekday() not in person.get("work_days", work_days(place)):
                continue
            start = max(opening, person.get("shift_start_minute", 480))
            end = min(closing, person.get("shift_end_minute", 1020))
            if start < end:
                windows.append(
                    (day + timedelta(minutes=start), day + timedelta(minutes=end))
                )
    merged = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def update_building_status(world: dict, *, observed: bool = False) -> None:
    now = datetime.fromisoformat(world["clock"])
    for place in world["places"]:
        if place["kind"] in {"home", "park", "station"}:
            continue
        if not place.get("business") and not any(
            p["workplace_id"] == place["id"] for p in world["people"]
        ):
            continue
        previous = place.get("operating_state", {})
        business = place.get("business", {})
        windows = _windows(world, place, now)
        scheduled = any(start <= now < end for start, end in windows)
        workers = [p for p in world["people"] if p["workplace_id"] == place["id"]]
        active = any(
            p.get("target_place_id") == place["id"]
            and now.weekday() in p.get("work_days", work_days(place))
            and p.get("shift_start_minute", 480)
            <= now.hour * 60 + now.minute
            < p.get("shift_end_minute", 1020)
            and p.get("activity", "").startswith("Working as")
            and not any(
                p.get(key)
                for key in ("direct_walk", "route", "on_train", "in_vehicle_id")
            )
            for p in workers
        )
        closed_since = None
        next_open = None
        if business.get("status") == "bankrupt":
            reason = business.get(
                "closure_reason", "The business could no longer cover its costs."
            )
            status = "Closed — bankrupt"
            closed_since = business.get("closed_at")
        elif not scheduled:
            today = any(
                now.weekday() in p.get("work_days", work_days(place)) for p in workers
            )
            reason = (
                "Outside scheduled opening hours."
                if today
                else "No shifts scheduled today."
            )
            status = "Closed" if today else "Closed — day off"
            closed_since = max((end for _, end in windows if end <= now), default=None)
            next_open = min(
                (start for start, _ in windows if start > now), default=None
            )
        elif not active:
            status = "Closed — no staff available"
            reason = "Scheduled staff are away or have paused work."
            if previous.get("status") == status:
                closed_since = previous.get("closed_since")
            elif observed:
                closed_since = now
        else:
            status = "Open"
            reason = "Staff are working here."
        place["operating_state"] = {
            "is_open": status == "Open",
            "status": status,
            "reason": reason,
            "closed_since": closed_since.isoformat(timespec="seconds")
            if isinstance(closed_since, datetime)
            else closed_since,
            "next_open_at": next_open.isoformat(timespec="seconds")
            if next_open
            else None,
        }
