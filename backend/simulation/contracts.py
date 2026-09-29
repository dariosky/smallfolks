"""Domain-state contracts shared by the simulation, storage and API boundary.

These TypedDicts describe the smallest stable vocabulary for the next simulation
steps.  They are intentionally not a second runtime model yet: the POC snapshot
remains JSON while its behaviour is being replaced incrementally.
"""

from typing import Literal, NotRequired, TypedDict


class Position(TypedDict):
    x: float
    y: float


class ClockState(TypedDict):
    elapsed_seconds: int
    paused: bool
    speed: float


class RevisionState(TypedDict):
    revision: int


class PlaceLocation(TypedDict):
    kind: Literal["place"]
    place_id: str


class RouteLocation(TypedDict):
    kind: Literal["route"]
    edge_id: str
    progress: float


class PlatformLocation(TypedDict):
    kind: Literal["platform"]
    station_id: str
    queue_id: NotRequired[str]


class VehicleLocation(TypedDict):
    kind: Literal["vehicle"]
    vehicle_id: str
    car_id: NotRequired[str]
    seat_id: NotRequired[str]


Location = PlaceLocation | RouteLocation | PlatformLocation | VehicleLocation


class ActivityState(TypedDict):
    id: str
    kind: str
    status: Literal["planned", "active", "complete", "cancelled"]
    started_at_seconds: NotRequired[int]
    ends_at_seconds: NotRequired[int]
    commitment_id: NotRequired[str]


class JourneyLeg(TypedDict):
    id: str
    mode: Literal["walk", "train", "car"]
    start_location: Location
    end_location: Location
    edge_ids: list[str]
    distance: float
    progress: float


class JourneyState(TypedDict):
    id: str
    status: Literal["planned", "active", "complete", "cancelled"]
    legs: list[JourneyLeg]
    active_leg_index: int


class Seat(TypedDict):
    id: str
    passenger_id: str | None


class CarriageState(TypedDict):
    id: str
    kind: Literal["locomotive", "passenger"]
    seats: list[Seat]


class TrainState(TypedDict):
    id: str
    service_state: Literal["travelling", "approaching", "stopped", "boarding", "departing"]
    distance: float
    carriages: list[CarriageState]


class StationQueueEntry(TypedDict):
    person_id: str
    arrived_at_seconds: int
    tie_breaker: str
    destination_station_id: str


class StationQueue(TypedDict):
    station_id: str
    entries: list[StationQueueEntry]
