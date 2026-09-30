"""Small integer-cent economy. All transfers share one saved ledger."""

from datetime import datetime, timedelta

BUSINESS_IDS = {
    "place:bakery",
    "place:supermarket",
    "place:florist",
    "place:lantern-bar",
    "place:cinema",
}
STARTING_PERSON_CENTS = 5_000
STARTING_HOUSEHOLD_CENTS = 10_000
STARTING_BUSINESS_CENTS = 100_000
WAGE_CENTS_PER_MINUTE = 20
DAILY_OVERHEAD_CENTS = 2_000
GROCERY_CENTS_PER_SERVING = 250
BAR_VISIT_CENTS = 1_200
CINEMA_VISIT_CENTS = 1_000
TAKEOVER_CAPITAL_CENTS = 8_000
PRICE_PERCENT_OPTIONS = (70, 80, 90, 100, 110, 120, 130)
BUSINESS_HOURS = {
    "place:supermarket": (8 * 60, 20 * 60),
    "place:florist": (9 * 60, 18 * 60),
    "place:bakery": (6 * 60, 18 * 60),
    "place:lantern-bar": (16 * 60, 23 * 60),
    "place:cinema": (15 * 60, 23 * 60),
}
# The fixture renders 15 named residents, while these customers represent the
# rest of the town. They are counted as sales, never as on-map visits.
REGIONAL_CUSTOMERS_PER_HOUR = {
    "place:bakery": 4,
    "place:supermarket": 5,
    "place:florist": 4,
    "place:lantern-bar": 4,
    "place:cinema": 5,
}
BASE_PRICES_CENTS = {
    "place:bakery": 600,
    "place:supermarket": 250,
    "place:florist": 800,
    "place:lantern-bar": BAR_VISIT_CENTS,
    "place:cinema": CINEMA_VISIT_CENTS,
}


def ensure_economy(world: dict) -> dict:
    """Add balances to older snapshots without erasing their existing state."""
    economy = world.setdefault("economy", {})
    economy.setdefault("household_contribution_percent", 50)
    economy.setdefault("treasury_cents", 100_000_000)
    economy.setdefault("outside_cents", 0)
    economy.setdefault("regional_customers_cents", 100_000_000)
    economy.setdefault("ledger", [])
    economy.setdefault(
        "next_ledger_id", economy["ledger"][-1]["id"] + 1 if economy["ledger"] else 1
    )
    for person in world["people"]:
        person.setdefault("money_cents", STARTING_PERSON_CENTS)
    for household in world["households"]:
        household.setdefault("money_cents", STARTING_HOUSEHOLD_CENTS)
    for place in world["places"]:
        if place["id"] in BUSINESS_IDS:
            business = place.setdefault("business", {})
            business.setdefault("balance_cents", STARTING_BUSINESS_CENTS)
            business.setdefault("status", "open")
            business.setdefault("price_percent", 100)
            business["base_unit_price_cents"] = BASE_PRICES_CENTS[place["id"]]
            business["unit_price_cents"] = price_cents(place)
            business.setdefault("owner_id", None)
            if "debts" not in business:
                # Older saves recorded closure but not the unpaid bill. Recover
                # the known failed obligation from the closure event if present.
                closure = next(
                    (
                        event["summary"]
                        for event in reversed(world.get("events", []))
                        if event["summary"].startswith(f"{place['name']} closed")
                    ),
                    "",
                )
                legacy_debt = (
                    WAGE_CENTS_PER_MINUTE * 15
                    if "workers" in closure
                    else DAILY_OVERHEAD_CENTS
                    if business["status"] == "bankrupt"
                    else 0
                )
                business["debts"] = (
                    [
                        {
                            "to": "outside",
                            "amount_cents": legacy_debt,
                            "reason": "Legacy unpaid bill",
                        }
                    ]
                    if legacy_debt
                    else []
                )
            business["debt_cents"] = sum(
                claim["amount_cents"] for claim in business["debts"]
            )
            business.setdefault("regional_visits_today", 0)
            business.setdefault("regional_sales_cents_today", 0)
    return economy


def _balance_ref(world: dict, account_id: str) -> tuple[dict, str]:
    if account_id == "bank":
        return world["economy"], "bank_cents"
    if account_id == "construction":
        return world["economy"], "construction_cents"
    if account_id == "treasury":
        return world["economy"], "treasury_cents"
    if account_id == "outside":
        return world["economy"], "outside_cents"
    if account_id == "regional_customers":
        return world["economy"], "regional_customers_cents"
    if account_id.startswith("person:"):
        return next(
            item for item in world["people"] if item["id"] == account_id
        ), "money_cents"
    if account_id.startswith("household:"):
        return next(
            item for item in world["households"] if item["id"] == account_id
        ), "money_cents"
    place = next(item for item in world["places"] if item["id"] == account_id)
    return place["dealership"] if account_id == "place:workshop" else place["business"], "balance_cents"


def can_pay(world: dict, account_id: str, cents: int) -> bool:
    account, field = _balance_ref(world, account_id)
    return cents >= 0 and account[field] >= cents


def transfer(
    world: dict, from_id: str, to_id: str, cents: int, reason: str, now: datetime
) -> bool:
    if not can_pay(world, from_id, cents):
        return False
    sender, sender_field = _balance_ref(world, from_id)
    recipient, recipient_field = _balance_ref(world, to_id)
    sender[sender_field] -= cents
    recipient[recipient_field] += cents
    ledger = world["economy"]["ledger"]
    ledger.append(
        {
            "id": world["economy"]["next_ledger_id"],
            "at": now.isoformat(timespec="seconds"),
            "from": from_id,
            "to": to_id,
            "amount_cents": cents,
            "reason": reason,
        }
    )
    world["economy"]["next_ledger_id"] += 1
    if len(ledger) > 200:
        del ledger[:-200]
    return True


def price_cents(place: dict) -> int:
    return BASE_PRICES_CENTS[place["id"]] * place["business"]["price_percent"] // 100


def purchase(
    world: dict, payer_id: str, place: dict, units: int, reason: str, now: datetime
) -> bool:
    if place["business"]["status"] != "open" or units <= 0:
        return False
    total = price_cents(place) * units
    if not transfer(world, payer_id, place["id"], total, reason, now):
        return False
    supplies = BASE_PRICES_CENTS[place["id"]] * units * 30 // 100
    transfer(world, place["id"], "outside", supplies, f"Supplies for {reason}", now)
    return True


def _regional_customers(place_id: str, price_percent: int) -> int:
    base = REGIONAL_CUSTOMERS_PER_HOUR[place_id]
    return max(0, (base * (200 - price_percent) + 50) // 100)


def _sale_price(place: dict) -> int:
    # A regional market customer buys two servings; a visible grocery trip
    # uses the household's actual serving count instead.
    return price_cents(place) * (2 if place["id"] == "place:supermarket" else 1)


def projected_daily_profit(world: dict, place: dict, price_percent: int) -> int:
    opening, closing = BUSINESS_HOURS[place["id"]]
    hours = (closing - opening) // 60
    buyers = _regional_customers(place["id"], price_percent) * hours
    gross_per_sale = BASE_PRICES_CENTS[place["id"]] * price_percent // 100
    if place["id"] == "place:supermarket":
        gross_per_sale *= 2
    supply_per_sale = (
        BASE_PRICES_CENTS[place["id"]]
        * (2 if place["id"] == "place:supermarket" else 1)
        * 30
        // 100
    )
    wages = sum(
        (
            person.get("shift_end_minute", 17 * 60)
            - person.get("shift_start_minute", 8 * 60)
        )
        * WAGE_CENTS_PER_MINUTE
        for person in world["people"]
        if person["workplace_id"] == place["id"]
    )
    return buyers * (gross_per_sale - supply_per_sale) - wages - DAILY_OVERHEAD_CENTS


def best_price_percent(world: dict, place: dict) -> int:
    return max(
        PRICE_PERCENT_OPTIONS,
        key=lambda percent: (
            projected_daily_profit(world, place, percent),
            -abs(percent - 100),
        ),
    )


def _record_debt(place: dict, creditor: str, cents: int, reason: str) -> None:
    place["business"]["debts"].append(
        {"to": creditor, "amount_cents": cents, "reason": reason}
    )
    place["business"]["debt_cents"] += cents


def take_over_business(
    world: dict, place_id: str, buyer_id: str, price_percent: int, now: datetime
) -> None:
    if price_percent not in PRICE_PERCENT_OPTIONS:
        raise ValueError("Choose one of the available price percentages.")
    place = next(
        (
            item
            for item in world["places"]
            if item["id"] == place_id and item["id"] in BUSINESS_IDS
        ),
        None,
    )
    buyer = next((item for item in world["people"] if item["id"] == buyer_id), None)
    if place is None or buyer is None:
        raise ValueError("Choose an existing business and resident.")
    business = place["business"]
    if business["status"] != "bankrupt":
        raise ValueError("Only a closed business can be taken over.")
    total = business["debt_cents"] + TAKEOVER_CAPITAL_CENTS
    if not can_pay(world, buyer_id, total):
        raise ValueError("The resident cannot cover the debt and working capital.")
    for claim in business["debts"]:
        transfer(
            world,
            buyer_id,
            claim["to"],
            claim["amount_cents"],
            f"Settled {place['name']} debt",
            now,
        )
    transfer(world, buyer_id, place_id, TAKEOVER_CAPITAL_CENTS, "Takeover capital", now)
    business["debts"] = []
    business["debt_cents"] = 0
    business["status"] = "open"
    business["owner_id"] = buyer_id
    business["price_percent"] = price_percent
    business["unit_price_cents"] = price_cents(place)
    world["events"].append(
        {
            "at": now.isoformat(timespec="minutes"),
            "summary": f"{buyer['name']} took over {place['name']}, settled its debt and set prices to {price_percent}% of the old level.",
        }
    )


def consider_takeovers(world: dict, now: datetime) -> None:
    for place in world["places"]:
        if place["id"] not in BUSINESS_IDS or place["business"]["status"] != "bankrupt":
            continue
        price_percent = best_price_percent(world, place)
        if projected_daily_profit(world, place, price_percent) <= 0:
            continue
        minimum_cash = place["business"]["debt_cents"] + TAKEOVER_CAPITAL_CENTS + 2_000
        workers = [
            person
            for person in world["people"]
            if person["workplace_id"] == place["id"]
        ]
        others = [
            person
            for person in world["people"]
            if person["workplace_id"] != place["id"]
        ]
        candidates = sorted(
            workers, key=lambda person: -person["money_cents"]
        ) + sorted(others, key=lambda person: -person["money_cents"])
        buyer = next(
            (
                person
                for person in candidates
                if person["money_cents"] >= minimum_cash
            ),
            None,
        )
        if buyer:
            take_over_business(world, place["id"], buyer["id"], price_percent, now)


def record_regional_sales(world: dict, now: datetime, is_open_and_staffed) -> None:
    hour_key = now.strftime("%Y-%m-%dT%H")
    day = now.date().isoformat()
    for place in world["places"]:
        if place["id"] not in BUSINESS_IDS or not is_open_and_staffed(
            world, place, now.hour * 60
        ):
            continue
        business = place["business"]
        if business.get("last_regional_hour") == hour_key:
            continue
        if business.get("regional_sales_date") != day:
            business["regional_visits_today"] = 0
            business["regional_sales_cents_today"] = 0
            business["regional_sales_date"] = day
        count = _regional_customers(place["id"], business["price_percent"])
        gross = count * _sale_price(place)
        supplies = (
            count
            * BASE_PRICES_CENTS[place["id"]]
            * (2 if place["id"] == "place:supermarket" else 1)
            * 30
            // 100
        )
        if transfer(
            world, "regional_customers", place["id"], gross, "Regional customers", now
        ):
            transfer(
                world,
                place["id"],
                "outside",
                supplies,
                "Supplies for regional sales",
                now,
            )
            business["regional_visits_today"] += count
            business["regional_sales_cents_today"] += gross
            business["last_regional_hour"] = hour_key


def reset_daily_sales(world: dict, now: datetime) -> None:
    for place in world["places"]:
        business = place.get("business")
        if business:
            business["regional_visits_today"] = 0
            business["regional_sales_cents_today"] = 0
            business["regional_sales_date"] = now.date().isoformat()


def pay_work_seconds(world: dict, person: dict, seconds: int, now: datetime) -> None:
    person["unpaid_work_seconds"] = person.get("unpaid_work_seconds", 0) + seconds
    if person["unpaid_work_seconds"] < 15 * 60:
        return
    person["unpaid_work_seconds"] -= 15 * 60
    employer_id = person["workplace_id"]
    employer = employer_id if employer_id in BUSINESS_IDS else "treasury"
    wage = WAGE_CENTS_PER_MINUTE * 15
    if not can_pay(world, employer, wage):
        if employer != "treasury":
            place = next(place for place in world["places"] if place["id"] == employer)
            place["business"]["status"] = "bankrupt"
            household_share = (
                wage * world["economy"]["household_contribution_percent"] // 100
            )
            if household_share:
                _record_debt(
                    place,
                    person["household_id"],
                    household_share,
                    "Unpaid shared wages",
                )
            if wage - household_share:
                _record_debt(
                    place, person["id"], wage - household_share, "Unpaid wages"
                )
            world["events"].append(
                {
                    "at": now.isoformat(timespec="minutes"),
                    "summary": f"{place['name']} closed after it could no longer pay its workers.",
                }
            )
        return
    percent = world["economy"]["household_contribution_percent"]
    household_share = wage * percent // 100
    personal_share = wage - household_share
    if household_share:
        transfer(
            world,
            employer,
            person["household_id"],
            household_share,
            "Shared wages",
            now,
        )
    if personal_share:
        transfer(world, employer, person["id"], personal_share, "Wages", now)

    record_income(person, personal_share, now)


def charge_daily_overhead(world: dict, now: datetime) -> None:
    for place in world["places"]:
        if place["id"] not in BUSINESS_IDS:
            continue
        business = place["business"]
        if business["status"] != "open":
            continue
        if not transfer(
            world, place["id"], "outside", DAILY_OVERHEAD_CENTS, "Operating costs", now
        ):
            business["status"] = "bankrupt"
            _record_debt(
                place, "outside", DAILY_OVERHEAD_CENTS, "Unpaid operating costs"
            )
            world["events"].append(
                {
                    "at": now.isoformat(timespec="minutes"),
                    "summary": f"{place['name']} closed after running out of money.",
                }
            )


def pay_owner_dividends(world: dict, now: datetime) -> None:
    if now.weekday() != 0:
        return
    for place in world["places"]:
        business = place.get("business")
        if not business or business["status"] != "open" or not business.get("owner_id"):
            continue
        scheduled_wages = sum(
            (
                person.get("shift_end_minute", 17 * 60)
                - person.get("shift_start_minute", 8 * 60)
            )
            * WAGE_CENTS_PER_MINUTE
            for person in world["people"]
            if person["workplace_id"] == place["id"]
        )
        reserve = 2 * (scheduled_wages + DAILY_OVERHEAD_CENTS)
        dividend = max(0, business["balance_cents"] - reserve) // 4
        if dividend:
            transfer(
                world,
                place["id"],
                business["owner_id"],
                dividend,
                "Owner dividend",
                now,
            )


def record_income(person: dict, cents: int, now: datetime) -> None:
    """Keep recent observed personal earnings for bank affordability checks."""
    history = person.setdefault("income_history", {})
    day = now.date().isoformat()
    history[day] = history.get(day, 0) + cents
    cutoff = (now.date() - timedelta(days=13)).isoformat()
    person["income_history"] = {key: value for key, value in history.items() if key >= cutoff}
