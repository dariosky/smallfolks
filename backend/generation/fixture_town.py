from copy import deepcopy

from generation.validators import validate_place_layout

GENERATION_VERSION = "poc-9"
SIMULATION_VERSION = "poc-1"

PEOPLE = [
    ("person:elena", "Elena Rossi", "place:rowan-1", "place:bakery", "Baker", "baker"),
    (
        "person:marco",
        "Marco Bianchi",
        "place:rowan-2",
        "place:workshop",
        "Mechanic",
        "mechanic",
    ),
    (
        "person:lea",
        "Lea Moretti",
        "place:rowan-3",
        "place:library",
        "Librarian",
        "librarian",
    ),
    (
        "person:tom",
        "Tom Alvarez",
        "place:rowan-4",
        "place:school",
        "Teacher",
        "teacher",
    ),
    ("person:ana", "Ana Silva", "place:rowan-5", "place:clinic", "Nurse", "nurse"),
    (
        "person:diego",
        "Diego Martin",
        "place:rowan-6",
        "place:supermarket",
        "Shopkeeper",
        "shopkeeper",
    ),
    (
        "person:sofia",
        "Sofia Costa",
        "place:rowan-7",
        "place:townhall",
        "Planner",
        "planner",
    ),
    (
        "person:lucas",
        "Lucas Weber",
        "place:rowan-8",
        "place:workshop",
        "Carpenter",
        "carpenter",
    ),
    (
        "person:nora",
        "Nora Klein",
        "place:rowan-9",
        "place:library",
        "Student",
        "student",
    ),
    (
        "person:bruno",
        "Bruno Meyer",
        "place:rowan-10",
        "place:rowan-10",
        "Gardener",
        "gardener",
    ),
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
    ("place:workshop", "Eastgate Workshop", "workplace", 1020, 150),
    ("place:library", "Willow Library", "workplace", 535, 590),
    ("place:school", "Smallfolk School", "workplace", 1010, 370),
    ("place:clinic", "Oak Clinic", "workplace", 1010, 550),
    ("place:townhall", "Town Hall", "workplace", 750, 570),
    ("place:park", "Mossy Common", "park", 540, 285),
    ("place:plaza", "Lantern Plaza", "park", 690, 285),
]


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
                "workplace_id": work_id,
                "role": role,
                "visual": visual,
                "palette": ["coral", "blue", "ochre", "plum", "green"][index % 5],
                "needs": {"hunger": 28 + index * 3, "rest": 22, "social": 35 + index},
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
    validate_place_layout(places)
    return {
        "id": f"world:poc-9-{seed}",
        "seed": seed,
        "generation_version": GENERATION_VERSION,
        "simulation_version": SIMULATION_VERSION,
        "clock": "2031-05-12T07:30:00",
        "paused": False,
        "places": places,
        "roads": [
            {"id": "road:grand-avenue", "points": [[45, 350], [1140, 350]]},
            {"id": "road:west-avenue", "points": [[365, 55], [365, 670]]},
            {"id": "road:centre-avenue", "points": [[700, 55], [700, 670]]},
            {"id": "road:east-avenue", "points": [[850, 55], [850, 670]]},
            {"id": "road:rowan-north", "points": [[45, 170], [365, 170]]},
            {"id": "road:rowan-middle", "points": [[45, 330], [365, 330]]},
            {"id": "road:rowan-south", "points": [[45, 520], [365, 520]]},
            {"id": "road:market-street", "points": [[365, 235], [850, 235]]},
            {"id": "road:orchard-street", "points": [[365, 520], [850, 520]]},
            {"id": "road:eastgate-lane", "points": [[850, 520], [1140, 520]]},
        ],
        "paths": [
            {"id": "path:rowan", "points": [[45, 145], [365, 145], [365, 520]]},
            {"id": "path:centre", "points": [[365, 210], [850, 210], [850, 620]]},
            {"id": "path:grand", "points": [[365, 375], [850, 375]]},
            {"id": "path:old-centre", "points": [[420, 185], [800, 185], [800, 350]]},
            {"id": "path:eastgate", "points": [[850, 250], [1080, 250], [1080, 520]]},
        ],
        "people": people,
        "pets": [
            {
                "id": "pet:pippin",
                "kind": "pet",
                "name": "Pippin",
                "guardian_id": "person:bruno",
                "position": {"x": 255, "y": 265},
                "activity": "Waiting for a morning walk",
                "target_place_id": "place:park",
                "explanation": "Bruno's daily pet-care commitment starts at 07:30.",
                "needs": {"energy": 72, "attention": 68},
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
            }
        ],
        "events": [
            {"at": "07:30", "summary": "A clear Monday begins in Smallfolk."},
            {"at": "07:30", "summary": "Bruno is due to walk Pippin in Mossy Common."},
        ],
    }


def clone_fixture(seed: int) -> dict:
    return deepcopy(build_fixture(seed))
