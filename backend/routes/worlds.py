import asyncio
from typing import Any

import anyio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlmodel import Session

from db import get_session
from services.world_stream import world_patch, world_streams
from services.worlds import (
    WorldRevisionConflictError,
    advance_world,
    create_world,
    get_entity,
    list_worlds,
    load_world,
    render_state,
    set_business_price,
    set_household_contribution,
    set_world_running,
    subscribe_world,
    take_over_world_business,
)

router = APIRouter(prefix="/worlds")


@router.websocket("/{world_id}/stream")
async def stream_world(websocket: WebSocket, world_id: str) -> None:
    loop = asyncio.get_running_loop()

    try:
        state, subscription = await anyio.to_thread.run_sync(subscribe_world, world_id, loop)
    except HTTPException:
        await websocket.close(code=1008)
        return

    async def send_updates():
        previous = state
        await asyncio.wait_for(websocket.send_json({"type": "snapshot", "world": state}), 10)
        while True:
            current = await subscription.queue.get()
            if current["revision"] <= previous["revision"]:
                continue
            operations = await asyncio.to_thread(world_patch, previous, current)
            if operations:
                await asyncio.wait_for(websocket.send_json({
                    "type": "patch", "base_revision": previous["revision"],
                    "revision": current["revision"], "operations": operations,
                }), 10)
            previous = current

    async def receive_disconnect():
        while True:
            await websocket.receive_text()

    tasks = []
    try:
        await websocket.accept()
        tasks = [asyncio.create_task(send_updates()), asyncio.create_task(receive_disconnect())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, TimeoutError, OSError):
        pass
    except asyncio.CancelledError:
        pass
    finally:
        world_streams.unsubscribe(world_id, subscription)
        for task in tasks:
            task.cancel()
        with anyio.CancelScope(shield=True):
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await websocket.close()
            except (WebSocketDisconnect, RuntimeError, OSError):
                pass


class CreateWorldInput(BaseModel):
    seed: int = Field(default=7341, ge=0, le=2_147_483_647)


class AdvanceWorldInput(BaseModel):
    minutes: int = Field(default=15, ge=1, le=240)
    expected_revision: int | None = Field(default=None, ge=0)


class RunWorldInput(BaseModel):
    running: bool
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    expected_revision: int | None = Field(default=None, ge=0)


class HouseholdContributionInput(BaseModel):
    percent: int = Field(ge=0, le=100)


class BusinessPriceInput(BaseModel):
    price_percent: int = Field(ge=70, le=130, multiple_of=10)


class BusinessTakeoverInput(BusinessPriceInput):
    buyer_id: str


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


@router.put("/{world_id}/economy/household-contribution")
def set_contribution(
    world_id: str, payload: HouseholdContributionInput, session: Session = Depends(get_session)
) -> dict[str, Any]:
    return set_household_contribution(session, world_id, payload.percent)


@router.post("/{world_id}/businesses/{place_id}/takeover")
def take_over(
    world_id: str, place_id: str, payload: BusinessTakeoverInput,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return take_over_world_business(session, world_id, place_id, payload.buyer_id, payload.price_percent)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/{world_id}/businesses/{place_id}/price")
def set_price(
    world_id: str, place_id: str, payload: BusinessPriceInput,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return set_business_price(session, world_id, place_id, payload.price_percent)
    except ValueError as error:
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
