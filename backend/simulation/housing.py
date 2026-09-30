"""Household-owned vehicles determine which homes need a side driveway."""

from math import hypot

from simulation.routing import nearest_road_point


def ensure_home_parking(world: dict) -> None:
    places = {place["id"]: place for place in world["places"]}
    homes = {
        member: places[household["home_place_id"]]
        for household in world["households"]
        for member in household["member_ids"]
    }
    for vehicle in world.get("vehicles", []):
        home = homes.get(vehicle.get("owner_id"))
        if home is None:
            continue
        if "driveway" not in home:
            if home.get("house_style") != "mansion":
                home["house_style"] = "large"
            add_driveway(world, home)
        # Upgrade the original shoulder parking once; never move a car mid-trip.
        if vehicle.get("state") == "parked" and not vehicle.get("parking_place_id") and not vehicle.get("reserved_by"):
            position = home_parking_point(world, home, vehicle["id"])
            if position is None:
                continue
            vehicle["position"] = position
            vehicle["parking_place_id"] = home["id"]
            vehicle["heading"] = 90


def add_driveway(world: dict, home: dict) -> None:
    """Create parking only after a paid upgrade, or for legacy car-owning homes."""
    if home.get("house_style") == "mansion" and home.get("driveway"):
        return
    position = {"x": home["position"]["x"] + 48, "y": home["position"]["y"] + 12}
    # Front access spurs are for entrance access; parking connects to a street.
    streets = [road for road in world["roads"] if not road["id"].startswith("road:access-")]
    home["driveway"] = {
        "parking_position": position,
        "road_position": nearest_road_point(streets or world["roads"], position),
    }


def home_parking_point(world: dict, home: dict, vehicle_id: str) -> dict | None:
    """Reserve an available driveway bay, including other residents' incoming cars."""
    driveway = home["driveway"]
    slots = driveway.get("parking_positions", [driveway["parking_position"]])
    occupied = [
        vehicle["position"] for vehicle in world["vehicles"]
        if vehicle["id"] != vehicle_id and vehicle.get("state") == "parked"
    ]
    occupied.extend(
        person["car_trip"]["parking_position"] for person in world["people"]
        if person.get("car_trip", {}).get("vehicle_id") != vehicle_id
        and person.get("car_trip", {}).get("destination_id") == home["id"]
        and "parking_position" in person["car_trip"]
    )
    return next((dict(slot) for slot in slots
                 if all(hypot(slot["x"] - point["x"], slot["y"] - point["y"]) >= 25
                        for point in occupied)), None)
