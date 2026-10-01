"""Daily regional funding and unconditional unemployment support."""

from simulation.economy import (
    BUSINESS_IDS,
    WAGE_CENTS_PER_MINUTE,
    can_pay,
    transfer,
)

SUPPORT_CENTS = 2_400


def eligible_adult(person: dict) -> bool:
    # The existing world has no ages; its student visual identifies students.
    return (
        person.get("visual") != "student"
        and person.get("role", "").lower() != "student"
    )


def unemployed(world: dict, person: dict) -> bool:
    workplace = next(
        (p for p in world["places"] if p["id"] == person.get("workplace_id")), None
    )
    return (
        workplace is not None
        and workplace.get("business", {}).get("status") == "bankrupt"
    )


def ensure_community(world: dict) -> None:
    economy = world["economy"]
    economy.setdefault("regional_grants_cents", 100_000_000_000)
    economy.setdefault("community_work_cents", 0)
    economy.setdefault("regional_grant_total_cents", 0)
    economy.setdefault("support_total_cents", 0)
    world.setdefault("municipal_projects", [])
    for person in world["people"]:
        if (
            person["id"] in {"person:maya", "person:sara"}
            and person.get("workplace_id") == "place:townhall"
            and person.get("role") == "Planner"
        ):
            person.update(role="Town handyman", visual="handyman")
            if person.get("activity") == "Working as planner":
                person.update(
                    activity="Waiting for a town work assignment",
                    explanation="Town Hall has reassigned this planner to park maintenance and community work.",
                )
    world.setdefault("volunteering_projects", [])
    world.setdefault("community_gardens", [])
    for place in world["places"]:
        if place["kind"] == "park":
            place.setdefault("cleanliness", 60)
            place.setdefault("cleanup_sessions", 0)
        if place["id"] == "place:library":
            place.setdefault("library_help_sessions", 0)


def pay_shared(
    world: dict, person: dict, cents: int, reason: str, now, *, account="treasury"
) -> bool:
    if not can_pay(world, account, cents):
        return False
    shared = cents * world["economy"]["household_contribution_percent"] // 100
    if shared:
        transfer(
            world, account, person["household_id"], shared, f"Shared {reason}", now
        )
    if cents - shared:
        transfer(world, account, person["id"], cents - shared, reason, now)
    return True


def fund_community(world: dict, now) -> None:
    """Fund a daily budget, not every expense; recheck changed eligibility."""
    ensure_community(world)
    economy = world["economy"]
    day = now.date().isoformat()
    if economy.get("public_budget_date") != day:
        economy.update(
            public_budget_date=day,
            public_spent_today_cents=0,
            regional_grant_today_cents=0,
            support_today_cents=0,
            legacy_commitments_today_cents=sum(
                p["wage_cents"]
                for p in world["volunteering_projects"]
                if p["status"] == "active" and not p.get("payment_reserved")
            ),
        )
    public_wages = sum(
        max(0, p.get("shift_end_minute", 1020) - p.get("shift_start_minute", 480))
        * WAGE_CENTS_PER_MINUTE
        for p in world["people"]
        if p.get("workplace_id") not in BUSINESS_IDS and now.weekday() in p["work_days"]
    )
    adults = [p for p in world["people"] if eligible_adult(p)]
    support = sum(
        SUPPORT_CENTS
        for p in adults
        if unemployed(world, p) or p.get("support_paid_date") == day
    )
    budget = (
        public_wages
        + support
        + SUPPORT_CENTS * len(adults)
        + economy["legacy_commitments_today_cents"]
    )
    economy["public_budget_cents"] = budget
    shortfall = max(
        0, budget - economy["public_spent_today_cents"] - economy["treasury_cents"]
    )
    if shortfall and transfer(
        world,
        "regional_grants",
        "treasury",
        shortfall,
        "Regional public-services grant",
        now,
    ):
        economy["regional_grant_today_cents"] += shortfall
        economy["regional_grant_total_cents"] += shortfall
        world["events"].append(
            {
                "at": now.isoformat(timespec="minutes"),
                "summary": f"Regional grant of €{shortfall / 100:.2f} funded Town Hall services.",
            }
        )
    # Old active projects gain real escrow on advance, without changing their terms.
    for project in world["volunteering_projects"]:
        if (
            project["status"] == "active"
            and not project.get("payment_reserved")
            and transfer(
                world,
                "treasury",
                "community_work",
                project["wage_cents"],
                "Reserve community-work payment",
                now,
            )
        ):
            project["payment_reserved"] = True
    if now.hour < 8:
        return
    for person in adults:
        if not unemployed(world, person) or person.get("support_paid_date") == day:
            continue
        if pay_shared(world, person, SUPPORT_CENTS, "Unemployment support", now):
            person["support_paid_date"] = day
            person["support_total_cents"] = (
                person.get("support_total_cents", 0) + SUPPORT_CENTS
            )
            economy["support_total_cents"] += SUPPORT_CENTS
            economy["support_today_cents"] += SUPPORT_CENTS
            world["events"].append(
                {
                    "at": now.isoformat(timespec="minutes"),
                    "summary": f"{person['name']} received €24 of unemployment support.",
                }
            )


def advance_community_conditions(world: dict, seconds: int) -> None:
    elapsed = world["economy"].get("cleanliness_elapsed_seconds", 0) + seconds
    hours, world["economy"]["cleanliness_elapsed_seconds"] = divmod(elapsed, 3600)
    if hours:
        for place in world["places"]:
            if place["kind"] == "park":
                place["cleanliness"] = max(0, place["cleanliness"] - hours)
