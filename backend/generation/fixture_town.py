from copy import deepcopy

from generation.city_layout import ensure_city_layout
from generation.validators import validate_place_layout
from simulation.buildings import update_building_status
from simulation.economy import ensure_economy
from simulation.housing import ensure_home_parking
from simulation.prosperity import ensure_prosperity
from simulation.schedules import ensure_schedules
from simulation.tick import STATIONS, rail_track
from simulation.versions import WORLD_FORMAT_VERSION

GENERATION_VERSION = "city-10"
SIMULATION_VERSION = "poc-4"

PEOPLE = [
    ("person:elena", "Elena Rossi", "place:rowan-1", "place:bakery", "Baker", "baker"),
    (
        "person:marco",
        "Marco Bianchi",
        "place:rowan-1",
        "place:workshop",
        "Mechanic",
        "mechanic",
    ),
    (
        "person:lea",
        "Lea Moretti",
        "place:rowan-2",
        "place:library",
        "Librarian",
        "librarian",
    ),
    (
        "person:tom",
        "Tom Alvarez",
        "place:rowan-2",
        "place:school",
        "Teacher",
        "teacher",
    ),
    ("person:ana", "Ana Silva", "place:rowan-3", "place:clinic", "Nurse", "nurse"),
    (
        "person:diego",
        "Diego Martin",
        "place:rowan-3",
        "place:supermarket",
        "Shopkeeper",
        "shopkeeper",
    ),
    (
        "person:sofia",
        "Sofia Costa",
        "place:rowan-4",
        "place:townhall",
        "Planner",
        "planner",
    ),
    (
        "person:lucas",
        "Lucas Weber",
        "place:rowan-4",
        "place:workshop",
        "Carpenter",
        "carpenter",
    ),
    (
        "person:nora",
        "Nora Klein",
        "place:rowan-5",
        "place:library",
        "Library assistant",
        "student",
    ),
    (
        "person:bruno",
        "Bruno Meyer",
        "place:rowan-5",
        "place:florist",
        "Gardener",
        "gardener",
    ),
    ("person:marta", "Marta Novak", "place:rowan-6", "place:lantern-bar", "Bartender", "bartender"),
    (
        "person:hugo",
        "Hugo Laurent",
        "place:rowan-7",
        "place:cinema",
        "Projectionist",
        "projectionist",
    ),
    ("person:irene", "Irene Costa", "place:rowan-7", "place:cinema", "Box office host", "host"),
    ("person:paolo", "Paolo Ricci", "place:rowan-8", "place:lantern-bar", "Server", "server"),
    ("person:clara", "Clara Weiss", "place:rowan-9", "place:cinema", "Usher", "usher"),
]

# A mix of shared family houses, couples, and residents living alone.
NEW_RESIDENTS = [
    ("alice", "Alice Romano", 11, "school", "Teacher", "teacher"),
    ("oliver", "Oliver Hart", 11, "school", "Teacher", "teacher"),
    ("emma", "Emma Romano", 11, "library", "Library assistant", "student"),
    ("leo", "Leo Hart", 11, "workshop", "Apprentice", "mechanic"),
    ("isabel", "Isabel Vega", 12, "clinic", "Nurse", "nurse"),
    ("mateo", "Mateo Vega", 12, "post-office", "Postal clerk", "host"),
    ("eva", "Eva Vega", 12, "townhall", "Planner", "planner"),
    ("felix", "Felix Vega", 12, "school", "Teacher", "teacher"),
    ("maya", "Maya Chen", 13, "townhall", "Planner", "planner"),
    ("noah", "Noah Chen", 13, "post-office", "Postal clerk", "host"),
    ("ada", "Ada Chen", 13, "library", "Librarian", "librarian"),
    ("sara", "Sara Lind", 14, "townhall", "Planner", "planner"),
    ("oscar", "Oscar Lind", 14, "clinic", "Nurse", "nurse"),
    ("julia", "Julia Marin", 15, "post-office", "Postal clerk", "host"),
    ("sam", "Sam Wilson", 16, "workshop", "Carpenter", "carpenter"),
]
PEOPLE.extend(
    (f"person:{slug}", name, f"place:rowan-{home}", f"place:{work}", role, visual)
    for slug, name, home, work, role, visual in NEW_RESIDENTS
)

SHIFT_WINDOWS = {
    "person:diego": (8 * 60, 20 * 60),
    "person:marta": (16 * 60, 23 * 60),
    "person:hugo": (15 * 60, 23 * 60),
    "person:irene": (16 * 60, 22 * 60),
    "person:paolo": (17 * 60, 23 * 60),
    "person:clara": (16 * 60, 22 * 60),
}
BOREDOM_START = [18, 22, 30, 25, 20, 24, 28, 19, 32, 21, 16, 26, 23, 19, 27]
SOCIAL_INCLINATIONS = [
    0.8,
    0.35,
    0.7,
    0.45,
    0.6,
    0.75,
    0.55,
    0.3,
    0.85,
    0.5,
    0.9,
    0.4,
    0.65,
    0.8,
    0.55,
]
CINEMA_INCLINATIONS = [
    0.35,
    0.55,
    0.85,
    0.25,
    0.45,
    0.3,
    0.6,
    0.4,
    0.9,
    0.2,
    0.35,
    0.6,
    0.55,
    0.3,
    0.75,
]

PLACES = [
    ("place:rowan-1", "Rowan House 1", "home", 95, 100),
    ("place:rowan-2", "Rowan House 2", "home", 190, 100),
    ("place:rowan-3", "Rowan House 3", "home", 285, 100),
    ("place:rowan-4", "Rowan House 4", "home", 95, 260),
    ("place:rowan-5", "Rowan House 5", "home", 190, 260),
    ("place:rowan-6", "Rowan House 6", "home", 285, 260),
    ("place:rowan-7", "Rowan House 7", "home", 95, 470),
    ("place:rowan-8", "Rowan House 8", "home", 190, 470),
    ("place:rowan-9", "Rowan House 9", "home", 285, 470),
    ("place:rowan-10", "Rowan House 10", "home", 95, 590),
    ("place:bakery", "Rosa Bakery", "bakery", 510, 135),
    ("place:post-office", "Little Post", "workplace", 660, 135),
    ("place:cinema", "Clover Cinema", "workplace", 780, 135),
    ("place:supermarket", "Hearth Market", "shop", 560, 435),
    ("place:florist", "Fern Florist", "shop", 700, 435),
    ("place:lantern-bar", "The Lantern Bar", "bar", 875, 550),
    ("place:workshop", "Eastgate Workshop", "workplace", 1020, 150),
    ("place:library", "Willow Library", "workplace", 535, 590),
    ("place:school", "SmallFolks School", "workplace", 1010, 435),
    ("place:clinic", "Oak Clinic", "workplace", 1010, 550),
    ("place:townhall", "Town Hall", "workplace", 750, 570),
    ("place:park", "Mossy Common", "park", 540, 285),
    ("place:plaza", "Lantern Plaza", "park", 690, 285),
]

PLACES.extend(
    (f"place:rowan-{number}", f"Willow House {number - 10}", "home", x, 850)
    for number, x in zip(range(11, 17), [120, 290, 460, 630, 800, 970], strict=True)
)

HOUSEHOLDS = [
    ("household:rowan-1", "place:rowan-1", ["person:elena", "person:marco"], 8),
    ("household:rowan-2", "place:rowan-2", ["person:lea", "person:tom"], 4),
    ("household:rowan-3", "place:rowan-3", ["person:ana", "person:diego"], 12),
    ("household:rowan-4", "place:rowan-4", ["person:sofia", "person:lucas"], 2),
    ("household:rowan-5", "place:rowan-5", ["person:nora", "person:bruno"], 8),
    ("household:rowan-6", "place:rowan-6", ["person:marta"], 4),
    ("household:rowan-7", "place:rowan-7", ["person:hugo", "person:irene"], 8),
    ("household:rowan-8", "place:rowan-8", ["person:paolo"], 3),
    ("household:rowan-9", "place:rowan-9", ["person:clara"], 3),
]
HOUSEHOLDS.extend(
    (f"household:rowan-{number}", f"place:rowan-{number}",
     [f"person:{slug}" for slug, _, home, *_ in NEW_RESIDENTS if home == number], 12)
    for number in range(11, 17)
)

HOUSEHOLD_BY_MEMBER = {
    member_id: household_id
    for household_id, _, member_ids, _ in HOUSEHOLDS
    for member_id in member_ids
}


def build_fixture(seed: int) -> dict:
    place_positions = {place_id: {"x": x, "y": y} for place_id, _, _, x, y in PLACES}
    people = []
    for index, (person_id, name, home_id, work_id, role, visual) in enumerate(PEOPLE):
        people.append(
            {
                "id": person_id,
                "kind": "person",
                "name": name,
                "home_place_id": home_id,
                "household_id": HOUSEHOLD_BY_MEMBER[person_id],
                "workplace_id": work_id,
                "role": role,
                "visual": visual,
                "palette": ["coral", "blue", "ochre", "plum", "green"][index % 5],
                "needs": {
                    "hunger": 28 + (index % 15) * 3,
                    "rest": 22,
                    "social": 35 + index % 15,
                    "boredom": BOREDOM_START[index % len(BOREDOM_START)],
                },
                "social_inclination": SOCIAL_INCLINATIONS[index % len(SOCIAL_INCLINATIONS)],
                "cinema_inclination": CINEMA_INCLINATIONS[index % len(CINEMA_INCLINATIONS)],
                "shift_start_minute": SHIFT_WINDOWS.get(person_id, (8 * 60, 17 * 60))[0],
                "shift_end_minute": SHIFT_WINDOWS.get(person_id, (8 * 60, 17 * 60))[1],
                "position": {
                    "x": place_positions[home_id]["x"],
                    "y": place_positions[home_id]["y"] + 28,
                },
                "activity": "Breakfast at home",
                "target_place_id": home_id,
                "explanation": "The day is beginning at home; work starts at 08:00.",
                "next_commitment": f"{role} shift at 08:00",
            }
        )
    places = [
        {"id": place_id, "name": name, "kind": kind, "position": {"x": x, "y": y}}
        for place_id, name, kind, x, y in PLACES
    ]
    households = [
        {
            "id": household_id,
            "home_place_id": home_id,
            "member_ids": member_ids,
            "food_servings": food_servings,
            "grocery_rotation_index": 0,
        }
        for household_id, home_id, member_ids, food_servings in HOUSEHOLDS
    ]
    for household in households:
        if len(household["member_ids"]) >= 3:
            next(place for place in places if place["id"] == household["home_place_id"])["house_style"] = "large"
    validate_place_layout(places)
    world = {
        "id": f"world:city-10-{seed}",
        "seed": seed,
        "world_format_version": WORLD_FORMAT_VERSION,
        "revision": 0,
        "generation_version": GENERATION_VERSION,
        "simulation_version": SIMULATION_VERSION,
        "clock": "2031-05-12T07:30:00",
        "simulation": {
            "elapsed_seconds": 0,
            "running": False,
            "speed": 1.0,
            "presentation_time_seconds": 0,
        },
        "places": places,
        "households": households,
        "roads": [],
        "paths": [],
        "people": people,
        "pets": [
            {
                "id": "pet:pippin",
                "kind": "pet",
                "name": "Pippin",
                "guardian_id": "person:bruno",
                "household_id": "household:rowan-5",
                "max_walk_autonomy_seconds": 12 * 60 * 60,
                "last_walk_at": "2031-05-11T21:30:00",
                "walk_rotation_index": 0,
                "position": {"x": 255, "y": 265},
                "activity": "Waiting for a morning walk",
                "target_place_id": "place:park",
                "explanation": "Bruno's daily pet-care commitment starts at 07:30.",
                "needs": {"energy": 72, "attention": 68, "walk_out": 83},
            }
        ],
        "vehicles": [
            {
                "id": "vehicle:lea",
                "kind": "vehicle",
                "name": "Lea's blue car",
                "owner_id": "person:lea",
                "position": {"x": 260, "y": 210},
                "state": "parked",
                "palette": "blue",
            },
            {
                "id": "vehicle:lucas",
                "kind": "vehicle",
                "name": "Lucas's red van",
                "owner_id": "person:lucas",
                "position": {"x": 260, "y": 160},
                "state": "parked",
                "palette": "coral",
            },
        ],
        "trains": [
            {
                "id": "train:folk-loop",
                "name": "Folk Loop",
                "stops": ["Rowan Halt", "Market Square", "Eastgate"],
                "capacity": 8,
                "car_capacity": 4,
                "track": rail_track(),
                "stations": [
                    {key: value for key, value in station.items() if key != "distance"}
                    for station in STATIONS.values()
                ],
            }
        ],
        "events": [],
    }
    world["map_size"] = {"width": 1200, "height": 1000}
    ensure_schedules(world)
    validate_place_layout(world["places"])
    ensure_city_layout(world)
    ensure_home_parking(world)
    ensure_economy(world)
    ensure_prosperity(world)
    update_building_status(world)
    return world


def clone_fixture(seed: int) -> dict:
    return deepcopy(build_fixture(seed))
