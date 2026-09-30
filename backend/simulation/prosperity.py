"""Saved aspirations, asset purchases, construction contracts and affordable loans."""

from datetime import datetime, timedelta
from hashlib import sha256

from simulation.economy import (
    BUSINESS_IDS,
    WAGE_CENTS_PER_MINUTE,
    best_price_percent,
    can_pay,
    projected_daily_profit,
    record_income,
    take_over_business,
    transfer,
)
from simulation.housing import add_driveway
from simulation.mansions import MANSION_PRICE, ensure_mansions
from simulation.routing import nearest_road_point, parking_point

CAR_PRICE = 100_000
SPORTS_CAR_PRICE = 250_000
SPORTS_PALETTES = ("ruby", "sapphire", "emerald", "amethyst", "champagne")
INVESTMENT_GOALS = ("home", "car", "sports_car", "shop", "mansion", "savings")
EXPANSION_PRICE = 150_000
HOUSE_PRICE = 300_000
SHOP_PRICE = 200_000
CASH_RESERVE = 20_000
LOAN_TERM_DAYS = 60
INTEREST_PERCENT = 8  # Fixed charge over the whole game-time loan, not an annual rate.
CONSTRUCTION_SECONDS = 7 * 8 * 60 * 60  # Seven full days of on-site work.
LABOR_CENTS = CONSTRUCTION_SECONDS // 60 * WAGE_CENTS_PER_MINUTE


def event(world: dict, now: datetime, summary: str) -> None:
    world["events"].append(
        {"at": now.isoformat(timespec="minutes"), "summary": summary}
    )


def ensure_prosperity(world: dict) -> None:
    ensure_mansions(world)
    economy = world["economy"]
    economy.setdefault("bank_cents", 10_000_000)
    economy.setdefault("construction_cents", 0)
    world.setdefault("loans", [])
    world.setdefault("construction_projects", [])
    for project in world["construction_projects"]:
        if (project["status"] != "completed"
            and not project["id"].endswith(":driveway")
            and project["required_seconds"] < CONSTRUCTION_SECONDS):
            extra_labor = (CONSTRUCTION_SECONDS - project["required_seconds"]) // 60 * WAGE_CENTS_PER_MINUTE
            # Keep the agreed price: move part of the materials budget into wages.
            if transfer(world, "outside", "construction", extra_labor,
                        "Reallocate expansion budget for longer construction",
                        datetime.fromisoformat(world["clock"])):
                project["required_seconds"] = CONSTRUCTION_SECONDS
    for person in world["people"]:
        person.setdefault("credit_score", 650)
        person.setdefault("income_history", {})
        if "investment_preferences" not in person:
            person["investment_preferences"] = sorted(
                INVESTMENT_GOALS,
                key=lambda goal: sha256(
                    f"{world['seed']}:{person['id']}:{goal}".encode()
                ).digest(),
            )
            person["mansion_preferences_version"] = 1
            refresh_aspiration(world, person)
        elif not person.get("mansion_preferences_version"):
            preferences = person["investment_preferences"]
            if "mansion" not in preferences:
                index = int.from_bytes(sha256(f"{world['seed']}:{person['id']}:mansion".encode()).digest()[:4], "big") % (len(preferences) + 1)
                preferences.insert(index, "mansion")
            person["mansion_preferences_version"] = 1
            refresh_aspiration(world, person)
    if not any(place["id"] == "place:bank" for place in world["places"]):
        bank = {
            "id": "place:bank",
            "name": "Willow Bank",
            "kind": "workplace",
            "position": {"x": 1010, "y": 285},
        }
        world["places"].append(bank)
        entrance = {"x": 1010, "y": 333}
        street = nearest_road_point(world["roads"], entrance)
        world["roads"].append(
            {
                "id": "road:access-place:bank",
                "points": [[street["x"], street["y"]], [entrance["x"], entrance["y"]]],
            }
        )
    workshop = next((p for p in world["places"] if p["id"] == "place:workshop"), None)
    if workshop:
        dealership = workshop.setdefault(
            "dealership", {"balance_cents": 50_000, "cars_sold": 0}
        )
        dealership["standard_price_cents"] = CAR_PRICE
        dealership["sports_price_cents"] = SPORTS_CAR_PRICE
    occupied = {household["home_place_id"] for household in world["households"]}
    for place in world["places"]:
        if place["kind"] == "home":
            place.setdefault(
                "owner_household_id",
                next(
                    (
                        h["id"]
                        for h in world["households"]
                        if h["home_place_id"] == place["id"]
                    ),
                    None,
                ),
            )
            if place["id"] not in occupied and place.get("owner_household_id") is None:
                place.setdefault("house_style", "large")
                place.setdefault("sale_price_cents", MANSION_PRICE if place.get("house_style") == "mansion" else HOUSE_PRICE)


def daily_income(person: dict, now: datetime) -> int:
    # Completed days only: one early wage block cannot pretend to be a full salary.
    cutoff = (now.date() - timedelta(days=7)).isoformat()
    history = [
        value
        for day, value in person.get("income_history", {}).items()
        if cutoff <= day < now.date().isoformat() and value > 0
    ]
    return sum(history) // len(history) if len(history) >= 3 else 0


def loan_eligible(world: dict, person: dict, principal: int, now: datetime) -> bool:
    work = next(
        place for place in world["places"] if place["id"] == person["workplace_id"]
    )
    installment = (principal * (100 + INTEREST_PERCENT) + 100 * LOAN_TERM_DAYS - 1) // (
        100 * LOAN_TERM_DAYS
    )
    active = [
        loan
        for loan in world["loans"]
        if loan["borrower_id"] == person["id"] and loan["status"] != "repaid"
    ]
    return (
        principal > 0
        and person["credit_score"] >= 650
        and work.get("business", {}).get("status") != "bankrupt"
        and not active
        and installment <= daily_income(person, now) // 4
        and can_pay(world, "bank", principal)
    )


def finance_purchase(
    world: dict, person: dict, cost: int, purpose: str, now: datetime
) -> bool:
    """Finance a validated purchase, preserving cash and requiring a 40% deposit."""
    available = max(0, person["money_cents"] - CASH_RESERVE)
    if available >= cost:
        return True
    principal = cost - available
    if (
        purpose not in {"car", "sports_car", "house", "home_expansion"}
        or available < cost * 40 // 100
    ):
        return False
    if not loan_eligible(world, person, principal, now):
        return False
    transfer(world, "bank", person["id"], principal, f"Loan for {purpose}", now)
    interest = (principal * INTEREST_PERCENT + 99) // 100
    total = principal + interest
    world["loans"].append(
        {
            "id": f"loan:{world['economy']['next_ledger_id']}",
            "borrower_id": person["id"],
            "purpose": purpose,
            "principal_cents": principal,
            "interest_cents": interest,
            "interest_percent": INTEREST_PERCENT,
            "remaining_cents": total,
            "installment_cents": (total + LOAN_TERM_DAYS - 1) // LOAN_TERM_DAYS,
            "next_payment_date": (now.date() + timedelta(days=1)).isoformat(),
            "term_days": LOAN_TERM_DAYS,
            "status": "active",
            "missed_payments": 0,
            "arrears_cents": 0,
            "issued_at": now.isoformat(timespec="seconds"),
        }
    )
    event(
        world,
        now,
        f"Willow Bank approved {person['name']}'s {purpose.replace('_', ' ')} loan with {INTEREST_PERCENT}% fixed interest over {LOAN_TERM_DAYS} days.",
    )
    return True


def collect_loan_payments(world: dict, now: datetime) -> None:
    for loan in world["loans"]:
        if loan["status"] == "repaid":
            continue
        person = next(p for p in world["people"] if p["id"] == loan["borrower_id"])
        # Accumulate due installments exactly once, including missed dates after reload.
        while loan["next_payment_date"] <= now.date().isoformat():
            due = min(
                loan["installment_cents"],
                loan["remaining_cents"] - loan["arrears_cents"],
            )
            loan["arrears_cents"] += max(0, due)
            loan["next_payment_date"] = (
                datetime.fromisoformat(loan["next_payment_date"]).date()
                + timedelta(days=1)
            ).isoformat()
            if due > 0 and not can_pay(world, person["id"], loan["arrears_cents"]):
                loan["missed_payments"] += 1
                person["credit_score"] = max(300, person["credit_score"] - 35)
                event(
                    world,
                    now,
                    f"{person['name']} missed a bank repayment; the unpaid installment remains due.",
                )
        due = min(loan["arrears_cents"], person["money_cents"])
        if due and transfer(
            world, person["id"], "bank", due, "Loan repayment with interest", now
        ):
            loan["remaining_cents"] -= due
            loan["arrears_cents"] -= due
            if loan["arrears_cents"] == 0:
                person["credit_score"] = min(850, person["credit_score"] + 2)
        loan["status"] = (
            "repaid"
            if loan["remaining_cents"] == 0
            else "overdue"
            if loan["arrears_cents"]
            else "active"
        )
        if loan["status"] == "repaid":
            loan["repaid_at"] = now.isoformat(timespec="seconds")
            event(
                world,
                now,
                f"{person['name']} repaid their bank loan, including interest.",
            )


def start_expansion(world: dict, person: dict, home: dict, now: datetime) -> bool:
    if home.get("house_style") in {"large", "mansion"} or home.get("construction_project_id"):
        return False
    workers = [p for p in world["people"] if p.get("visual") == "carpenter"]
    if not workers or not finance_purchase(
        world, person, EXPANSION_PRICE, "home_expansion", now
    ):
        return False
    transfer(
        world,
        person["id"],
        "outside",
        EXPANSION_PRICE - LABOR_CENTS,
        "House expansion materials",
        now,
    )
    transfer(
        world,
        person["id"],
        "construction",
        LABOR_CENTS,
        "Construction wages in escrow",
        now,
    )
    project_id = f"construction:{home['id']}"
    home["construction_project_id"] = project_id
    world["construction_projects"].append(
        {
            "id": project_id,
            "home_place_id": home["id"],
            "buyer_id": person["id"],
            "worker_id": None,
            "status": "queued",
            "worked_seconds": 0,
            "required_seconds": CONSTRUCTION_SECONDS,
            "paid_work_seconds": 0,
            "includes_driveway": True,
            "cost_cents": EXPANSION_PRICE,
        }
    )
    event(
        world,
        now,
        f"{person['name']} commissioned a larger {home['name']} with a side driveway.",
    )
    return True


def assign_construction(world: dict) -> None:
    busy = {
        p["worker_id"]
        for p in world["construction_projects"]
        if p["status"] == "building"
    }
    workers = [
        p
        for p in world["people"]
        if p.get("visual") == "carpenter" and p["id"] not in busy
    ]
    for project in world["construction_projects"]:
        if project["status"] == "queued" and workers:
            worker = workers.pop(0)
            project["worker_id"] = worker["id"]
            project["status"] = "building"


def work_on_expansion(
    world: dict, person: dict, project: dict, seconds: int, now: datetime
) -> None:
    if project["status"] == "completed" or seconds <= 0:
        return
    worked = min(seconds, project["required_seconds"] - project["worked_seconds"])
    project["worked_seconds"] += worked
    payable_seconds = (
        project["worked_seconds"] // 900 * 900 - project["paid_work_seconds"]
    )
    if payable_seconds:
        wage = payable_seconds // 60 * WAGE_CENTS_PER_MINUTE
        shared = wage * world["economy"]["household_contribution_percent"] // 100
        transfer(
            world,
            "construction",
            person["household_id"],
            shared,
            "Construction shared wages",
            now,
        )
        transfer(
            world,
            "construction",
            person["id"],
            wage - shared,
            "Construction wages",
            now,
        )
        record_income(person, wage - shared, now)
        project["paid_work_seconds"] += payable_seconds
    if project["worked_seconds"] == project["required_seconds"]:
        home = next(p for p in world["places"] if p["id"] == project["home_place_id"])
        home["house_style"] = "large"
        add_driveway(world, home)
        home.pop("construction_project_id", None)
        project["status"] = "completed"
        event(
            world,
            now,
            f"{person['name']} finished expanding {home['name']}; its driveway is ready.",
        )


def car_purchase_available(world: dict, person: dict, model: str) -> bool:
    household = next(
        h for h in world["households"] if h["id"] == person["household_id"]
    )
    cars = [v for v in world["vehicles"] if v["owner_id"] in household["member_ids"]]
    home = next(p for p in world["places"] if p["id"] == household["home_place_id"])
    capacity = len(home.get("driveway", {}).get("parking_positions", [None]))
    existing = next((car for car in cars if car["owner_id"] == person["id"]), None)
    if model == "standard":
        return existing is None and len(cars) < capacity
    return (existing is None and len(cars) < capacity) or (
        existing is not None and len(cars) <= capacity
        and existing.get("model", "standard") != "sports"
    )


def purchase_affordable(world: dict, person: dict, cost: int, now: datetime) -> bool:
    available = max(0, person["money_cents"] - CASH_RESERVE)
    return available >= cost or (
        available >= cost * 40 // 100
        and loan_eligible(world, person, cost - available, now)
    )


def workshop_parking(world: dict, exclude_vehicle_id: str | None = None) -> dict | None:
    workshop = next(p for p in world["places"] if p["id"] == "place:workshop")
    streets = [r for r in world["roads"] if not r["id"].startswith("road:access-")]
    base = parking_point(streets or world["roads"], workshop["position"])
    return next(
        (
            {"x": base["x"] + offset, "y": base["y"]}
            for offset in (0, 32, -32, 64, -64, 96, -96)
            if all(
                (v["position"]["x"] - base["x"] - offset) ** 2
                + (v["position"]["y"] - base["y"]) ** 2
                >= 25**2
                for v in world["vehicles"]
                if v["id"] != exclude_vehicle_id
            )
        ),
        None,
    )


def buy_car(
    world: dict, person: dict, home: dict, now: datetime, model: str = "standard"
) -> bool:
    if model not in {"standard", "sports"} or not car_purchase_available(
        world, person, model
    ):
        return False
    if home.get("house_style") not in {"large", "mansion"} or not home.get("driveway"):
        return False
    workshop = next(p for p in world["places"] if p["id"] == "place:workshop")
    # Purchases are arrival-gated, including bringing an existing car for replacement.
    if (
        person.get("target_place_id") != workshop["id"]
        or person.get("direct_walk")
        or person.get("route")
        or person.get("car_trip")
        or person.get("train_trip")
        or person.get("in_vehicle_id")
        or (person["position"]["x"] - workshop["position"]["x"]) ** 2
        + (person["position"]["y"] - workshop["position"]["y"]) ** 2
        > 55**2
    ):
        return False
    existing = next(
        (v for v in world["vehicles"] if v["owner_id"] == person["id"]), None
    )
    if existing and (
        existing.get("state") != "parked"
        or existing.get("reserved_by")
        or existing.get("driver_id")
        or existing.get("parking_place_id") != workshop["id"]
    ):
        return False
    position = dict(existing["position"]) if existing else workshop_parking(world)
    if position is None:
        return False
    price = SPORTS_CAR_PRICE if model == "sports" else CAR_PRICE
    purpose = "sports_car" if model == "sports" else "car"
    if not finance_purchase(world, person, price, purpose, now):
        return False
    transfer(
        world,
        person["id"],
        workshop["id"],
        price,
        "Sports car purchase" if model == "sports" else "Car purchase",
        now,
    )
    transfer(
        world,
        workshop["id"],
        "outside",
        price * 85 // 100,
        "Workshop vehicle supplier",
        now,
    )
    workshop["dealership"]["cars_sold"] += 1
    palette = (
        SPORTS_PALETTES[
            int.from_bytes(
                sha256(f"{world['seed']}:{person['id']}:paint".encode()).digest()[:4],
                "big",
            )
            % len(SPORTS_PALETTES)
        ]
        if model == "sports"
        else "blue"
    )
    vehicle = existing or {"id": f"vehicle:{person['id'].split(':', 1)[1]}"}
    if existing is None:
        world["vehicles"].append(vehicle)
    vehicle.update(
        {
            "kind": "vehicle",
            "name": f"{person['name'].split()[0]}'s {'luxury sports car' if model == 'sports' else 'car'}",
            "owner_id": person["id"],
            "model": model,
            "position": position,
            "state": "parked",
            "parking_place_id": workshop["id"],
            "heading": 0,
            "palette": palette,
            "speed_units_per_minute": 144 if model == "sports" else 90,
        }
    )
    person.pop("vehicle_purchase", None)
    event(
        world,
        now,
        f"{person['name']} {'replaced their car with' if existing else 'bought'} a {'luxury sports car' if model == 'sports' else 'car'} at {workshop['name']}.",
    )
    return True


def buy_house(world: dict, person: dict, new_home: dict, now: datetime) -> bool:
    household = next(
        h for h in world["households"] if h["id"] == person["household_id"]
    )
    old_home = next(p for p in world["places"] if p["id"] == household["home_place_id"])
    if (
        new_home["kind"] != "home"
        or new_home.get("owner_household_id") is not None
        or not new_home.get("sale_price_cents")
        or new_home.get("house_style") not in {"large", "mansion"}
        or old_home.get("construction_project_id")
        or any(h["home_place_id"] == new_home["id"] for h in world["households"])
    ):
        return False
    if not finance_purchase(world, person, new_home["sale_price_cents"], "house", now):
        return False
    transfer(
        world,
        person["id"],
        "treasury",
        new_home["sale_price_cents"],
        "House purchase",
        now,
    )
    old_home["owner_household_id"] = household[
        "id"
    ]  # Retain the old property; no invented sale proceeds.
    new_home["owner_household_id"] = household["id"]
    new_home.pop("sale_price_cents", None)
    add_driveway(world, new_home)
    household["home_place_id"] = new_home["id"]
    for member in world["people"]:
        if member["id"] in household["member_ids"]:
            member["home_place_id"] = new_home["id"]
    if new_home.get("house_style") == "mansion":
        for member in world["people"]:
            if member["id"] in household["member_ids"]:
                refresh_aspiration(world, member)
    # Existing journeys and car positions remain real; the next home decision routes there.
    event(
        world,
        now,
        f"{person['name']}'s household bought {new_home['name']} and is moving into "
        + ("a walled mansion with extensive gardens." if new_home.get("house_style") == "mansion" else "a larger home."),
    )
    return True


def buy_shop(world: dict, person: dict, shop: dict, now: datetime) -> bool:
    business = shop["business"]
    if shop["id"] not in BUSINESS_IDS or business["owner_id"] == person["id"]:
        return False
    price_percent = best_price_percent(world, shop)
    if projected_daily_profit(world, shop, price_percent) <= 0:
        return False
    if business["status"] == "bankrupt":
        if person["money_cents"] < business["debt_cents"] + 8_000 + CASH_RESERVE:
            return False
        take_over_business(world, shop["id"], person["id"], price_percent, now)
        return True
    if (
        business["owner_id"] is not None
        or person["money_cents"] < SHOP_PRICE + CASH_RESERVE
    ):
        return False
    transfer(world, person["id"], "treasury", SHOP_PRICE, "Shop purchase", now)
    business["owner_id"] = person["id"]
    event(
        world,
        now,
        f"{person['name']} bought {shop['name']} to grow their business portfolio.",
    )
    return True


def preferred_goal(world: dict, person: dict) -> str:
    household = next(
        h for h in world["households"] if h["id"] == person["household_id"]
    )
    home = next(p for p in world["places"] if p["id"] == household["home_place_id"])
    for goal in person["investment_preferences"]:
        if goal == "home" and home.get("house_style") not in {"large", "mansion"}:
            return goal
        if goal == "mansion" and home.get("house_style") == "large" and any(
            place.get("house_style") == "mansion" and place.get("sale_price_cents")
            and place.get("owner_household_id") is None
            for place in world["places"]
        ):
            return goal
        if goal == "car" and car_purchase_available(world, person, "standard"):
            return goal
        if goal == "sports_car" and car_purchase_available(world, person, "sports"):
            return goal
        if goal == "shop" and any(
            p["id"] in BUSINESS_IDS
            and (
                p["business"]["owner_id"] is None
                or p["business"]["status"] == "bankrupt"
            )
            and p["business"]["owner_id"] != person["id"]
            for p in world["places"]
        ):
            return goal
        if goal == "savings" and person["money_cents"] < 100_000:
            return goal
    return "savings"


def refresh_aspiration(world: dict, person: dict) -> None:
    goal = preferred_goal(world, person)
    person["investment_goal"] = goal
    if goal == "mansion":
        person["investment_target_cents"] = min(
            place["sale_price_cents"] for place in world["places"]
            if place.get("house_style") == "mansion" and place.get("sale_price_cents")
            and place.get("owner_household_id") is None
        )
    else:
        person.pop("investment_target_cents", None)
    person["aspiration"] = {
        "home": "Saving for a larger home and driveway.",
        "mansion": "Saving for an upper-class villa with a vast walled garden and two-car driveway.",
        "car": "Saving for a practical everyday car from the workshop.",
        "sports_car": "Saving for a fast, luxurious sports car from the workshop.",
        "shop": "Saving to invest in a profitable shop.",
        "savings": "Building a comfortable savings cushion before a big purchase.",
    }[goal]


def consider_prosperity(world: dict, now: datetime) -> None:
    """Residents pursue their own saved preferences, with one household purchase per day."""
    day = now.date().isoformat()
    if now.hour < 9 or world["economy"].get("last_prosperity_date") == day:
        return
    world["economy"]["last_prosperity_date"] = day
    purchased = set()
    for person in sorted(world["people"], key=lambda p: (-p["money_cents"], p["id"])):
        if person["household_id"] in purchased or person.get("vehicle_purchase"):
            continue
        household = next(
            h for h in world["households"] if h["id"] == person["household_id"]
        )
        home = next(p for p in world["places"] if p["id"] == household["home_place_id"])
        refresh_aspiration(world, person)
        if (
            household["food_servings"] < len(household["member_ids"])
            or household["money_cents"] < 5_000
        ):
            person["aspiration"] = (
                "Building a reserve for household food before investing."
            )
            continue
        if home.get("construction_project_id"):
            person["aspiration"] += (
                " Waiting for the hired builder to finish the driveway."
            )
            continue
        goal = person["investment_goal"]
        success = False
        if goal == "home":
            for vacant in world["places"]:
                if (
                    vacant.get("sale_price_cents")
                    and vacant.get("house_style") == "large"
                    and person["money_cents"]
                    >= vacant["sale_price_cents"] * 40 // 100 + CASH_RESERVE
                ):
                    success = buy_house(world, person, vacant, now)
                    if success:
                        break
            if not success:
                success = start_expansion(world, person, home, now)
        elif goal == "mansion":
            for vacant in world["places"]:
                if vacant.get("house_style") == "mansion" and buy_house(world, person, vacant, now):
                    success = True
                    break
        elif goal in {"car", "sports_car"}:
            if not home.get("driveway"):
                success = (
                    start_driveway(world, person, home, now)
                    if home.get("house_style") == "large"
                    else start_expansion(world, person, home, now)
                )
            elif purchase_affordable(
                world,
                person,
                SPORTS_CAR_PRICE if goal == "sports_car" else CAR_PRICE,
                now,
            ):
                person["vehicle_purchase"] = {
                    "model": "sports" if goal == "sports_car" else "standard",
                    "planned_at": now.isoformat(timespec="seconds"),
                }
                person["aspiration"] = (
                    "Visiting the workshop to buy a luxury sports car."
                    if goal == "sports_car"
                    else "Visiting the workshop to buy an everyday car."
                )
                success = True
        elif goal == "shop":
            for shop in world["places"]:
                if shop["id"] in BUSINESS_IDS and buy_shop(world, person, shop, now):
                    success = True
                    break
        if success:
            purchased.add(person["household_id"])
            if goal == "mansion":
                refresh_aspiration(world, person)


def start_driveway(world: dict, person: dict, home: dict, now: datetime) -> bool:
    # Same crew and arrival-gated work; a driveway is a smaller two-hour contract.
    if home.get("driveway") or home.get("construction_project_id"):
        return False
    if not any(p.get("visual") == "carpenter" for p in world["people"]):
        return False
    cost = 40_000
    labor = 120 * WAGE_CENTS_PER_MINUTE
    if not finance_purchase(world, person, cost, "home_expansion", now):
        return False
    transfer(world, person["id"], "outside", cost - labor, "Driveway materials", now)
    transfer(
        world, person["id"], "construction", labor, "Construction wages in escrow", now
    )
    project_id = f"construction:{home['id']}:driveway"
    home["construction_project_id"] = project_id
    world["construction_projects"].append(
        {
            "id": project_id,
            "home_place_id": home["id"],
            "buyer_id": person["id"],
            "worker_id": None,
            "status": "queued",
            "worked_seconds": 0,
            "required_seconds": 120 * 60,
            "paid_work_seconds": 0,
            "includes_driveway": True,
            "cost_cents": cost,
        }
    )
    event(
        world,
        now,
        f"{person['name']} hired a builder to add a driveway to {home['name']}.",
    )
    return True
