"""A spacious villa district added without moving existing residents or buildings."""

MANSION_PRICE = 1_500_000
MANSION_DISTRICT_VERSION = 1


def ensure_mansions(world: dict) -> None:
    if world.get("generation_version") != "city-10" or world.get("mansion_district_version") == MANSION_DISTRICT_VERSION:
        return
    size = world.setdefault("map_size", {"width": 1200, "height": 1000})
    size["height"] = max(size["height"], 1450)
    roads = [
        {"id": "road:estate-link", "points": [[500, 920], [500, 1370]]},
        {"id": "road:estate-boulevard", "points": [[60, 1370], [1080, 1370]]},
    ]
    for slug, name, x in [("cedar-villa", "Cedar Grove Villa", 250), ("magnolia-villa", "Magnolia Estate", 800)]:
        place_id = f"place:{slug}"
        if not any(place["id"] == place_id for place in world["places"]):
            slots = [{"x": x + offset, "y": 1228} for offset in (82, 114)]
            world["places"].append({
                "id": place_id, "name": name, "kind": "home", "house_style": "mansion",
                "position": {"x": x, "y": 1160}, "entrance": {"x": x, "y": 1208},
                "estate_gate": {"x": x, "y": 1315},
                "owner_household_id": None, "sale_price_cents": MANSION_PRICE,
                "driveway": {"parking_position": slots[0], "parking_positions": slots,
                             "road_position": {"x": x, "y": 1370}},
            })
        roads.extend([
            {"id": f"road:access-{place_id}", "points": [[x, 1370], [x, 1208]]},
            {"id": f"road:access-{place_id}:courtyard", "points": [[x, 1260], [x + 114, 1260]]},
            *[{"id": f"road:access-{place_id}:parking-{index}",
               "points": [[x + offset, 1260], [x + offset, 1228]]}
              for index, offset in enumerate((82, 114))],
        ])
    existing = {road["id"] for road in world["roads"]}
    world["roads"].extend(road for road in roads if road["id"] not in existing)
    world["mansion_district_version"] = MANSION_DISTRICT_VERSION


def inside_mansion(world: dict, position: dict) -> bool:
    return any(
        place.get("house_style") == "mansion"
        and abs(position["x"] - place["position"]["x"]) <= 155
        and -125 <= position["y"] - place["position"]["y"] <= 155
        for place in world["places"]
    )
