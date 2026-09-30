FOOTPRINTS = {
    "restaurant": (116, 86),
    "home": (78, 74),
    "bakery": (116, 86),
    "shop": (116, 86),
    "bar": (116, 86),
    "workplace": (116, 86),
    "park": (142, 104),
}


def place_footprint(place: dict) -> tuple[int, int]:
    if place.get("house_style") == "mansion":
        return (310, 310)
    return FOOTPRINTS[place["kind"]]


def validate_place_layout(places: list[dict]) -> None:
    """Reject generated town layouts whose usable place footprints overlap."""
    for index, place in enumerate(places):
        width, height = place_footprint(place)
        left = place["position"]["x"] - width / 2
        top = place["position"]["y"] - height / 2
        right = left + width
        bottom = top + height
        for other in places[index + 1 :]:
            other_width, other_height = place_footprint(other)
            other_left = other["position"]["x"] - other_width / 2
            other_top = other["position"]["y"] - other_height / 2
            other_right = other_left + other_width
            other_bottom = other_top + other_height
            if left < other_right and right > other_left and top < other_bottom and bottom > other_top:
                raise ValueError(f"Place footprints overlap: {place['id']} and {other['id']}")
