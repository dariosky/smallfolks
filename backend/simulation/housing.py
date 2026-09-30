"""Household-owned vehicles determine which homes need a side driveway."""

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
            position = {"x": home["position"]["x"] + 48, "y": home["position"]["y"] + 12}
            home["house_style"] = "large"
            home["driveway"] = {
                "parking_position": position,
                "road_position": nearest_road_point(world["roads"], position),
            }
        # Upgrade the original shoulder parking once; never move a car mid-trip.
        if vehicle.get("state") == "parked" and not vehicle.get("parking_place_id") and not vehicle.get("reserved_by"):
            vehicle["position"] = dict(home["driveway"]["parking_position"])
            vehicle["parking_place_id"] = home["id"]
            vehicle["heading"] = 90
