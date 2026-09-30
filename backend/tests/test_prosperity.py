from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from generation.fixture_town import build_fixture
from simulation.prosperity import (
    CAR_PRICE,
    CASH_RESERVE,
    CONSTRUCTION_SECONDS,
    assign_construction,
    buy_car,
    buy_house,
    buy_shop,
    collect_loan_payments,
    consider_prosperity,
    finance_purchase,
    loan_eligible,
    start_expansion,
    work_on_expansion,
)
from simulation.tick import _position_at, advance, advance_seconds
from simulation.versions import migrate_snapshot


def resident(world, slug="elena"):
    return next(
        person for person in world["people"] if person["id"] == f"person:{slug}"
    )


def place(world, slug="rowan-1"):
    return next(item for item in world["places"] if item["id"] == f"place:{slug}")


def seasoned(person, now, income=6000):
    person["income_history"] = {
        (now.date() - timedelta(days=n)).isoformat(): income for n in range(1, 5)
    }


def cash_total(world):
    return (
        sum(person["money_cents"] for person in world["people"])
        + sum(h["money_cents"] for h in world["households"])
        + sum(p.get("business", {}).get("balance_cents", 0) for p in world["places"])
        + sum(p.get("dealership", {}).get("balance_cents", 0) for p in world["places"])
        + sum(
            world["economy"][key]
            for key in [
                "treasury_cents",
                "outside_cents",
                "regional_customers_cents",
                "bank_cents",
                "construction_cents",
            ]
        )
    )


def test_loan_funds_car_once_and_returns_principal_plus_interest():
    world = build_fixture(7341)
    person = resident(world, "lea")
    world["vehicles"] = [v for v in world["vehicles"] if v["owner_id"] != person["id"]]
    home = place(world, "rowan-2")
    now = datetime.fromisoformat(world["clock"])
    seasoned(person, now)
    person["money_cents"] = 60_000
    total, bank_before = cash_total(world), world["economy"]["bank_cents"]
    person["position"] = _position_at(person, place(world, "workshop"))
    person["target_place_id"] = "place:workshop"
    assert buy_car(world, person, home, now)
    assert person["money_cents"] == CASH_RESERVE
    loan = world["loans"][0]
    assert loan["principal_cents"] == CAR_PRICE - 40_000
    assert loan["interest_cents"] == 4800
    assert not buy_car(world, person, home, now)
    person["money_cents"] += 100_000
    for day in range(1, 61):
        collect_loan_payments(world, now + timedelta(days=day))
        remaining = loan["remaining_cents"]
        collect_loan_payments(world, now + timedelta(days=day))
        assert loan["remaining_cents"] == remaining
    assert loan["status"] == "repaid"
    assert loan["remaining_cents"] == 0
    assert world["economy"]["bank_cents"] == bank_before + 4800
    assert cash_total(world) == total + 100_000


@pytest.mark.parametrize(
    "failure",
    [
        "no_history",
        "bad_credit",
        "unemployed",
        "low_income",
        "empty_bank",
        "existing_loan",
    ],
)
def test_bank_refuses_unaffordable_or_uncreditworthy_loans_without_transfers(failure):
    world = build_fixture(7341)
    person = resident(world)
    now = datetime.fromisoformat(world["clock"])
    seasoned(person, now)
    if failure == "no_history":
        person["income_history"] = {}
    elif failure == "bad_credit":
        person["credit_score"] = 600
    elif failure == "unemployed":
        place(world, "bakery")["business"]["status"] = "bankrupt"
    elif failure == "low_income":
        seasoned(person, now, 500)
    elif failure == "empty_bank":
        world["economy"]["bank_cents"] = 0
    else:
        world["loans"].append({"borrower_id": person["id"], "status": "overdue"})
    before = deepcopy(world)
    assert not loan_eligible(world, person, 60_000, now)
    assert world == before


def test_missed_installment_survives_reload_and_can_be_caught_up():
    world = build_fixture(7341)
    person = resident(world)
    now = datetime.fromisoformat(world["clock"])
    seasoned(person, now)
    person["money_cents"] = 60_000
    assert finance_purchase(world, person, CAR_PRICE, "car", now)
    person["money_cents"] = 0
    collect_loan_payments(world, now + timedelta(days=1))
    loan = world["loans"][0]
    remaining = loan["remaining_cents"]
    assert loan["status"] == "overdue"
    assert loan["missed_payments"] == 1
    assert person["credit_score"] == 615
    collect_loan_payments(world, now + timedelta(days=1))
    assert loan["missed_payments"] == 1
    loaded = migrate_snapshot(world)
    resident(loaded)["money_cents"] = 10_000
    collect_loan_payments(loaded, now + timedelta(days=1))
    assert loaded["loans"][0]["status"] == "active"
    assert (
        loaded["loans"][0]["remaining_cents"] == remaining - loan["installment_cents"]
    )


def test_builder_must_arrive_and_work_before_home_grows_with_balanced_payroll():
    world = build_fixture(7341)
    person, home = resident(world), place(world)
    person["money_cents"] = 200_000
    total = cash_total(world)
    now = datetime.fromisoformat(world["clock"])
    assert start_expansion(world, person, home, now)
    assert not start_expansion(world, person, home, now)
    project = world["construction_projects"][0]
    assign_construction(world)
    worker = next(p for p in world["people"] if p["id"] == project["worker_id"])
    worker["position"] = {"x": 900, "y": 300}
    worker.pop("car_trip", None)
    world["clock"] = "2031-05-12T09:00:00"
    advance_seconds(world, 5)
    assert worker["activity"].startswith("Walking to build")
    assert project["worked_seconds"] == 0
    assert "house_style" not in home
    assert "driveway" not in home
    advance(world, 60)
    assert 0 < project["worked_seconds"] < CONSTRUCTION_SECONDS
    loaded = migrate_snapshot(world)
    loaded_project = loaded["construction_projects"][0]
    assert loaded_project["worked_seconds"] == project["worked_seconds"]
    loaded_worker = resident(loaded, worker["id"].split(":")[1])
    work_on_expansion(loaded, loaded_worker, loaded_project, CONSTRUCTION_SECONDS, now)
    assert place(loaded)["house_style"] == "large"
    assert place(loaded)["driveway"]
    assert loaded_project["status"] == "completed"
    assert loaded["economy"]["construction_cents"] == 0
    assert cash_total(loaded) == total
    before = deepcopy(loaded)
    work_on_expansion(loaded, loaded_worker, loaded_project, 60, now)
    # Completed projects do not pay wages again or announce completion twice.
    assert loaded == before


def test_resident_can_own_two_profitable_shops_without_borrowing():
    world = build_fixture(7341)
    person = resident(world)
    person["money_cents"] = 500_000
    now = datetime.fromisoformat(world["clock"])
    total = cash_total(world)
    assert buy_shop(world, person, place(world, "bakery"), now)
    assert buy_shop(world, person, place(world, "florist"), now)
    assert not buy_shop(world, person, place(world, "bakery"), now)
    assert (
        len(
            [
                p
                for p in world["places"]
                if p.get("business", {}).get("owner_id") == person["id"]
            ]
        )
        == 2
    )
    assert world["loans"] == []
    assert cash_total(world) == total


def test_buying_a_larger_house_moves_household_contracts_without_teleporting():
    world = build_fixture(7341)
    person = resident(world)
    person["money_cents"] = 400_000
    now = datetime.fromisoformat(world["clock"])
    new_home = place(world, "rowan-10")
    positions = {p["id"]: dict(p["position"]) for p in world["people"]}
    total = cash_total(world)
    assert buy_house(world, person, new_home, now)
    assert not buy_house(world, resident(world, "ana"), new_home, now)
    assert resident(world)["home_place_id"] == new_home["id"]
    assert resident(world, "marco")["home_place_id"] == new_home["id"]
    assert {p["id"]: p["position"] for p in world["people"]} == positions
    assert cash_total(world) == total


def test_daily_decisions_keep_reserves_and_do_not_duplicate_projects():
    world = build_fixture(7341)
    person = resident(world)
    person["investment_preferences"] = ["home", "car", "shop", "sports_car", "savings"]
    person["money_cents"] = 200_000
    now = datetime.fromisoformat("2031-05-12T09:00:00")
    consider_prosperity(world, now)
    assert len(world["construction_projects"]) == 1
    assert person["money_cents"] >= CASH_RESERVE
    before = deepcopy(world)
    consider_prosperity(world, now)
    assert world == before


def test_legacy_upgrade_adds_bank_and_credit_without_overwriting_savings():
    world = build_fixture(7341)
    world["places"] = [p for p in world["places"] if p["id"] != "place:bank"]
    for key in ["loans", "construction_projects"]:
        world.pop(key)
    for key in ["bank_cents", "construction_cents"]:
        world["economy"].pop(key)
    resident(world)["money_cents"] = 123_456
    upgraded = migrate_snapshot(world)
    assert resident(upgraded)["money_cents"] == 123_456
    assert place(upgraded, "bank")["name"] == "Willow Bank"
    assert (
        len(
            [p for p in migrate_snapshot(upgraded)["places"] if p["id"] == "place:bank"]
        )
        == 1
    )
    assert "loans" not in world


def test_full_engine_construction_is_save_safe_and_time_grouping_independent():
    world = build_fixture(7341)
    person = resident(world)
    person["money_cents"] = 200_000
    assert start_expansion(
        world, person, place(world), datetime.fromisoformat(world["clock"])
    )
    assign_construction(world)
    project = world["construction_projects"][0]
    worker = resident(world, project["worker_id"].split(":")[1])
    worker["position"] = _position_at(worker, place(world))
    worker["target_place_id"] = place(world)["id"]
    world["clock"] = "2031-05-12T09:00:00"
    other = deepcopy(world)
    advance(world, 20)
    for _ in range(20):
        advance(other, 1)
    assert world == other
    assert (
        migrate_snapshot(world)["construction_projects"]
        == world["construction_projects"]
    )


def test_partial_repayment_reduces_debt_and_keeps_the_unpaid_balance_due():
    world = build_fixture(7341)
    person = resident(world)
    now = datetime.fromisoformat(world["clock"])
    seasoned(person, now)
    person["money_cents"] = 60_000
    assert finance_purchase(world, person, CAR_PRICE, "car", now)
    person["money_cents"] = 100
    loan = world["loans"][0]
    initial = loan["remaining_cents"]
    collect_loan_payments(world, now + timedelta(days=1))
    assert person["money_cents"] == 0
    assert loan["remaining_cents"] == initial - 100
    assert loan["arrears_cents"] == loan["installment_cents"] - 100
    assert loan["status"] == "overdue"


def test_engine_finishes_paid_construction_over_two_work_days():
    world = build_fixture(7341)
    person = resident(world)
    person["money_cents"] = 200_000
    assert start_expansion(
        world, person, place(world), datetime.fromisoformat(world["clock"])
    )
    advance(world, 30 * 60)
    project = world["construction_projects"][0]
    assert project["status"] == "completed"
    assert project["worked_seconds"] == project["required_seconds"]
    assert place(world)["house_style"] == "large"
    assert place(world)["driveway"]
    assert world["economy"]["construction_cents"] == 0
