from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from db import get_session
from services.worlds import (
    advance_world,
    create_world,
    get_entity,
    list_worlds,
    load_world,
    render_state,
)

router = APIRouter(prefix="/worlds")


class CreateWorldInput(BaseModel):
    seed: int = Field(default=7341, ge=0, le=2_147_483_647)


class AdvanceWorldInput(BaseModel):
    minutes: int = Field(default=15, ge=1, le=240)


@router.get("")
def list_saved_worlds(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return list_worlds(session)


@router.post("")
def create(payload: CreateWorldInput, session: Session = Depends(get_session)) -> dict[str, Any]:
    return create_world(session, payload.seed)


@router.get("/{world_id}")
def get_world(world_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    return load_world(session, world_id)


@router.post("/{world_id}/advance")
def advance_time(world_id: str, payload: AdvanceWorldInput, session: Session = Depends(get_session)) -> dict[str, Any]:
    return advance_world(session, world_id, payload.minutes)


@router.get("/{world_id}/render-state")
def get_render_state(world_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    return render_state(load_world(session, world_id))


@router.get("/{world_id}/entities/{entity_id}")
def inspect_entity(world_id: str, entity_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    return get_entity(session, world_id, entity_id)


@router.get("/{world_id}/events")
def get_events(world_id: str, session: Session = Depends(get_session)) -> list[dict[str, str]]:
    return load_world(session, world_id)["events"]
