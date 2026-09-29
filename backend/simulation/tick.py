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
            onboard = sum(
                1 for neighbour in world["people"] if neighbour.get("on_train")
            )
            if onboard < TRAIN_CAPACITY:
                person["on_train"] = True
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
        person["train_departure_id"] = departure["id"]
        person["train_arrival_id"] = arrival["id"]
    else:
        person.pop("on_train", None)
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


def advance(world: dict, minutes: int) -> dict:
    if minutes > 1:
        for _ in range(minutes):
            advance(world, 1)
        return world
    previous = datetime.fromisoformat(world["clock"])
    now = previous + timedelta(minutes=minutes)
    world["clock"] = now.isoformat(timespec="minutes")
    hour = now.hour + now.minute / 60
    current_minutes = now.hour * 60 + now.minute
    minutes_since_service_start = current_minutes - (7 * 60 + 30)
    for person in world["people"]:
        person["needs"]["hunger"] = min(100, person["needs"]["hunger"] + minutes // 12)
        person["needs"]["rest"] = min(100, person["needs"]["rest"] + minutes // 20)
        home = _place(world, person["home_place_id"])
        work = _place(world, person["workplace_id"])
        market = _place(world, "place:supermarket")
        train_journey = _train_journey(home, work)
        commute_minutes = _walking_minutes(home, work)
        commute_start = 8 * 60 - commute_minutes
        if train_journey:
            commute_start = (
                7 * 60
                + 30
                + train_journey["departure_minute"]
                - train_journey["access_minutes"]
            )
        if person["id"] == "person:bruno" and 7.5 <= hour < 8.0:
            park = _place(world, "place:park")
            _move_to(
                person,
                park,
                "Walking Pippin",
                "Pippin needs attention, and Bruno's pet-care commitment is due now.",
                "Gardening work at 09:00",
            )
        elif commute_start <= current_minutes < 8 * 60:
            elapsed_minutes = current_minutes - commute_start
            if train_journey:
                _take_train_to(
                    world,
                    person,
                    home,
                    work,
                    train_journey,
                    minutes_since_service_start,
                    f"{person['role']} shift at 08:00",
                )
            else:
                _walk_to(
                    person,
                    home,
                    work,
                    elapsed_minutes / commute_minutes,
                    f"{person['role']} shift at 08:00",
                )
        elif 8 <= hour < 17:
            _move_to(
                person,
                work,
                f"Working as {person['role'].lower()}",
                f"It is a scheduled {person['role'].lower()} shift, so this commitment takes priority.",
                "Shop for food after work",
            )
        elif (
            17 * 60 <= current_minutes < 17 * 60 + _walking_minutes(work, market)
            and person["needs"]["hunger"] >= 45
        ):
            _walk_to(
                person,
                work,
                market,
                (current_minutes - 17 * 60) / _walking_minutes(work, market),
                "Buy food at Hearth Market",
            )
        elif (
            17 * 60 + _walking_minutes(work, market) <= current_minutes < 18.5 * 60
            and person["needs"]["hunger"] >= 45
        ):
            _move_to(
                person,
                market,
                "Buying food",
                "Hunger is high after work and Hearth Market is open and reachable.",
                "Return home for dinner",
            )
            person["needs"]["hunger"] = 24
        else:
            _move_to(
                person,
                home,
                "At home",
                "There is no urgent commitment; home offers rest and dinner.",
                f"{person['role']} shift tomorrow at 08:00",
            )

    train_state = _service_state(minutes_since_service_start)
    world["trains"][0]["state"] = {
        **train_state,
        "capacity": TRAIN_CAPACITY,
        "car_capacity": TRAIN_CAR_CAPACITY,
        "passenger_ids": [
            person["id"] for person in world["people"] if person.get("on_train")
        ],
    }

    pippin = world["pets"][0]
    if 7.5 <= hour < 8.0:
        pippin["position"] = dict(_place(world, "place:park")["position"])
        pippin["activity"] = "Walking with Bruno"
        pippin["explanation"] = "Bruno is fulfilling Pippin's morning care commitment."
    else:
        home = _place(world, "place:rowan-10")
        pippin["position"] = {
            "x": home["position"]["x"] - 17,
            "y": home["position"]["y"] + 28,
        }
        pippin["activity"] = "Resting at home"
        pippin["explanation"] = "The morning walk is complete; Pippin is safe at home."
    if minutes:
        world["events"].append(
            {
                "at": now.strftime("%H:%M"),
                "summary": f"The town advanced {minutes} minutes to {now.strftime('%H:%M')}.",
            }
        )
    world["events"] = world["events"][-12:]
    return world
