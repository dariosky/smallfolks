"""Shared street geometry for new and existing fixture cities."""

from simulation.routing import nearest_road_point

CITY_LAYOUT_VERSION = 1


def ensure_city_layout(world: dict) -> None:
    if world.get("city_layout_version") == CITY_LAYOUT_VERSION:
        return
    world.pop("mansion_district_version", None)
    streets = [
        {"id": "road:grand-avenue", "points": [[45, 350], [1140, 350]]},
        {"id": "road:west-avenue", "points": [[365, 55], [365, 920]]},
        {"id": "road:east-avenue", "points": [[850, 55], [850, 350]]},
        {"id": "road:east-boundary", "points": [[1140, 235], [1140, 670]]},
        {"id": "road:rowan-north", "points": [[45, 170], [365, 170]]},
        {"id": "road:rowan-south", "points": [[45, 520], [365, 520]]},
        {"id": "road:market-street", "points": [[365, 235], [1140, 235]]},
        {"id": "road:orchard-street", "points": [[365, 520], [1140, 520]]},
        {"id": "road:south-avenue", "points": [[45, 670], [1140, 670]]},
        {"id": "road:willow-street", "points": [[60, 920], [1080, 920]]},
        {"id": "road:east-link", "points": [[850, 670], [850, 920]]},
    ]
    world["roads"] = list(streets)
    # The old white paths duplicated streets or ran directly along their centres.
    world["paths"] = []
    for place in world["places"]:
        if place.get("house_style") == "mansion":
            continue
        x, y = place["position"]["x"], place["position"]["y"]
        entrance = {"x": x, "y": y + 48}
        place["entrance"] = entrance
        # Approach from the south, never through the building from its north side.
        candidates = [
            (start, end) for road in streets
            for start, end in zip(road["points"], road["points"][1:])
            if start[1] == end[1] and start[0] <= x <= end[0] and start[1] >= entrance["y"]
        ]
        street_y = min(start[1] for start, _ in candidates)
        world["roads"].append({
            "id": f"road:access-{place['id']}",
            "points": [[x, street_y], [x, y + (48 if place["kind"] in {"home", "park"} else 34)]],
        })
        if place.get("driveway"):
            place["driveway"]["road_position"] = nearest_road_point(
                streets, place["driveway"]["parking_position"]
            )
    world["city_layout_version"] = CITY_LAYOUT_VERSION
