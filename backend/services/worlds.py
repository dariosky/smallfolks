import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock

from fastapi import HTTPException
from sqlmodel import Session, select

from db import engine
from generation.fixture_town import clone_fixture
from persistence.models import WorldSnapshot
from services.world_stream import world_streams
from simulation.buildings import update_building_status
from simulation.economy import PRICE_PERCENT_OPTIONS, price_cents, take_over_business
from simulation.tick import LOGICAL_TICK_SECONDS, advance, advance_seconds
from simulation.versions import (
    UnsupportedWorldFormatError,
    migrate_snapshot,
    snapshot_format_version,
)

_world_locks: defaultdict[str, Lock] = defaultdict(Lock)


class WorldRevisionConflictError(Exception):
    """A command was based on a state that has already changed."""


def _check_revision(state: dict, expected_revision: int | None) -> None:
    if expected_revision is not None and expected_revision != state.get("revision", 0):
        raise WorldRevisionConflictError(
            f"World revision is {state.get('revision', 0)}, not {expected_revision}."
        )


def create_world(session: Session, seed: int) -> dict:
    # Apply the schedule at the fixture's current clock, so commuters who need
    # to leave before 08:00 do not wait for the first browser tick to decide.
    state = advance(clone_fixture(seed), 0)
    snapshot = WorldSnapshot(
        id=state["id"],
        seed=seed,
        world_format_version=snapshot_format_version(state),
        state_json=json.dumps(state),
    )
    existing = session.get(WorldSnapshot, snapshot.id)
    if existing:
        return load_world(session, snapshot.id)
    session.add(snapshot)
    session.commit()
    return state


def list_worlds(session: Session) -> list[dict]:
    snapshots = session.exec(
        select(WorldSnapshot).order_by(WorldSnapshot.updated_at.desc())
    ).all()
    return [
        {
            "id": snapshot.id,
            "seed": snapshot.seed,
            "world_format_version": snapshot.world_format_version,
            "updated_at": snapshot.updated_at.isoformat(),
        }
        for snapshot in snapshots
    ]


def load_world(session: Session, world_id: str) -> dict:
    snapshot = session.get(WorldSnapshot, world_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="World not found")
    try:
        return migrate_snapshot(json.loads(snapshot.state_json))
    except UnsupportedWorldFormatError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This saved world is incompatible with the current app.",
                "reason": str(error),
                "world_id": world_id,
            },
        ) from error


def subscribe_world(world_id: str, loop: asyncio.AbstractEventLoop):
    # Read and subscribe under the mutation lock so a commit cannot fall between them.
    with _world_locks[world_id], Session(engine) as session:
        state = load_world(session, world_id)
        return state, world_streams.subscribe(world_id, loop)


def save_world(session: Session, state: dict) -> None:
    snapshot = session.get(WorldSnapshot, state["id"])
    if snapshot is None:  # pragma: no cover - protected by load_world
        raise HTTPException(status_code=404, detail="World not found")
    snapshot.state_json = json.dumps(state)
    snapshot.world_format_version = snapshot_format_version(state)
    snapshot.updated_at = datetime.now(UTC)
    session.add(snapshot)
    session.commit()
    world_streams.publish(state)


def advance_world(
    session: Session, world_id: str, minutes: int, expected_revision: int | None = None
) -> dict:
    with _world_locks[world_id]:
        state = load_world(session, world_id)
        _check_revision(state, expected_revision)
        state = advance(state, minutes)
        state["revision"] = state.get("revision", 0) + 1
        save_world(session, state)
        return state


def set_household_contribution(session: Session, world_id: str, percent: int) -> dict:
    with _world_locks[world_id]:
        state = load_world(session, world_id)
        state["economy"]["household_contribution_percent"] = percent
        state["revision"] = state.get("revision", 0) + 1
        save_world(session, state)
        return state


def take_over_world_business(
    session: Session, world_id: str, place_id: str, buyer_id: str, price_percent: int
) -> dict:
    with _world_locks[world_id]:
        state = load_world(session, world_id)
        take_over_business(state, place_id, buyer_id, price_percent, datetime.fromisoformat(state["clock"]))
        update_building_status(state, observed=True)
        state["revision"] = state.get("revision", 0) + 1
        save_world(session, state)
        return state


def set_business_price(session: Session, world_id: str, place_id: str, price_percent: int) -> dict:
    with _world_locks[world_id]:
        state = load_world(session, world_id)
        place = next((place for place in state["places"] if place["id"] == place_id), None)
        if (place is None or not place.get("business") or place["business"]["status"] != "open"
            or not place["business"].get("owner_id") or price_percent not in PRICE_PERCENT_OPTIONS):
            raise ValueError("An owned, open business and valid price are required.")
        place["business"]["price_percent"] = price_percent
        place["business"]["unit_price_cents"] = price_cents(place)
        state["revision"] = state.get("revision", 0) + 1
        save_world(session, state)
        return state


def set_world_running(
    session: Session,
    world_id: str,
    running: bool,
    speed: float,
    expected_revision: int | None = None,
) -> dict:
    with _world_locks[world_id]:
        state = load_world(session, world_id)
        _check_revision(state, expected_revision)
        simulation = state.setdefault("simulation", {"elapsed_seconds": 0})
        simulation["running"] = running
        simulation["speed"] = speed
        state["revision"] = state.get("revision", 0) + 1
        save_world(session, state)
        return state


def tick_running_worlds() -> None:
    """Advance open worlds at one server-owned logical cadence.

    There is intentionally no catch-up calculation: a stopped server or unloaded
    process leaves a world at its last saved simulation time.
    """
    with Session(engine) as session:
        world_ids = list(session.exec(select(WorldSnapshot.id)).all())
    for world_id in world_ids:
        with _world_locks[world_id], Session(engine) as session:
            state = load_world(session, world_id)
            simulation = state.get("simulation", {})
            if not simulation.get("running", False):
                continue
            logical_seconds = round(LOGICAL_TICK_SECONDS * simulation.get("speed", 1.0))
            if logical_seconds <= 0:
                continue
            advance_seconds(state, logical_seconds)
            state["revision"] = state.get("revision", 0) + 1
            save_world(session, state)


def get_entity(session: Session, world_id: str, entity_id: str) -> dict:
    world = load_world(session, world_id)
    for collection in ("people", "pets", "vehicles", "places"):
        for entity in world[collection]:
            if entity["id"] == entity_id:
                return entity
    raise HTTPException(status_code=404, detail="Entity not found")


def render_state(world: dict) -> dict:
    entities = []
    for collection in ("people", "pets", "vehicles"):
        for entity in world[collection]:
            entities.append(
                {
                    "id": entity["id"],
                    "kind": entity["kind"],
                    "name": entity["name"],
                    "position": entity["position"],
                    "state": entity.get("activity", entity.get("state", "parked")),
                    "palette": entity.get("palette", "green"),
                }
            )
    return {
        "clock": world["clock"],
        "roads": world["roads"],
        "paths": world["paths"],
        "places": world["places"],
        "entities": entities,
    }
