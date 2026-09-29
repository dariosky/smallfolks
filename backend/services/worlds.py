import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from generation.fixture_town import clone_fixture
from persistence.models import WorldSnapshot
from simulation.tick import advance


def create_world(session: Session, seed: int) -> dict:
    # Apply the schedule at the fixture's current clock, so commuters who need
    # to leave before 08:00 do not wait for the first browser tick to decide.
    state = advance(clone_fixture(seed), 0)
    snapshot = WorldSnapshot(id=state["id"], seed=seed, state_json=json.dumps(state))
    existing = session.get(WorldSnapshot, snapshot.id)
    if existing:
        return json.loads(existing.state_json)
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
            "updated_at": snapshot.updated_at.isoformat(),
        }
        for snapshot in snapshots
    ]


def load_world(session: Session, world_id: str) -> dict:
    snapshot = session.get(WorldSnapshot, world_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="World not found")
    return json.loads(snapshot.state_json)


def save_world(session: Session, state: dict) -> None:
    snapshot = session.get(WorldSnapshot, state["id"])
    if snapshot is None:  # pragma: no cover - protected by load_world
        raise HTTPException(status_code=404, detail="World not found")
    snapshot.state_json = json.dumps(state)
    snapshot.updated_at = datetime.now(UTC)
    session.add(snapshot)
    session.commit()


def advance_world(session: Session, world_id: str, minutes: int) -> dict:
    state = advance(load_world(session, world_id), minutes)
    save_world(session, state)
    return state


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
