from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from db import get_session
from services.worlds import (
    WorldRevisionConflictError,
    advance_world,
    create_world,
    get_entity,
    list_worlds,
    load_world,
    render_state,
    set_world_running,
)

router = APIRouter(prefix="/worlds")


class CreateWorldInput(BaseModel):
    seed: int = Field(default=7341, ge=0, le=2_147_483_647)


class AdvanceWorldInput(BaseModel):
    minutes: int = Field(default=15, ge=1, le=240)
    expected_revision: int | None = Field(default=None, ge=0)


class RunWorldInput(BaseModel):
    running: bool
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    expected_revision: int | None = Field(default=None, ge=0)


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
    try:
        return advance_world(session, world_id, payload.minutes, payload.expected_revision)
    except WorldRevisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{world_id}/run")
def set_running(
    world_id: str, payload: RunWorldInput, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        return set_world_running(
            session,
            world_id,
            payload.running,
            payload.speed,
            payload.expected_revision,
        )
    except WorldRevisionConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{world_id}/render-state")
def get_render_state(world_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    return render_state(load_world(session, world_id))


@router.get("/{world_id}/entities/{entity_id}")
def inspect_entity(world_id: str, entity_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    return get_entity(session, world_id, entity_id)


@router.get("/{world_id}/events")
def get_events(world_id: str, session: Session = Depends(get_session)) -> list[dict[str, str]]:
    return load_world(session, world_id)["events"]
