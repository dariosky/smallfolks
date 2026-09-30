"""Compatibility policy for durable world snapshots."""

from copy import deepcopy
from typing import Any

from generation.city_layout import ensure_city_layout
from simulation.economy import ensure_economy
from simulation.housing import ensure_home_parking
from simulation.prosperity import ensure_prosperity
from simulation.tick import STATIONS, rail_track

WORLD_FORMAT_VERSION = 1
LEGACY_WORLD_FORMAT_VERSION = 0


class UnsupportedWorldFormatError(ValueError):
    """A snapshot needs a migration that this build does not provide."""


def snapshot_format_version(state: dict[str, Any]) -> int:
    value = state.get("world_format_version", LEGACY_WORLD_FORMAT_VERSION)
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnsupportedWorldFormatError("World format version must be an integer.")
    return value


def migrate_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """Return a current-format view without silently writing a user's save.

    Format 0 is the original POC JSON shape.  Its only migration is additive:
    old snapshots receive a command revision and an explicit format marker.
    The result is persisted only after an intentional state-changing command.
    """
    source_version = snapshot_format_version(state)
    if source_version > WORLD_FORMAT_VERSION:
        raise UnsupportedWorldFormatError(
            f"World format {source_version} is newer than this app supports "
            f"(latest supported: {WORLD_FORMAT_VERSION})."
        )
    if source_version < LEGACY_WORLD_FORMAT_VERSION:
        raise UnsupportedWorldFormatError(
            f"World format {source_version} is no longer supported. Restore it with an older build."
        )

    migrated = deepcopy(state)
    if source_version == LEGACY_WORLD_FORMAT_VERSION:
        migrated["world_format_version"] = WORLD_FORMAT_VERSION
        migrated.setdefault("revision", 0)
    migrated.setdefault(
        "simulation",
        {
            "elapsed_seconds": 0,
            "presentation_time_seconds": 0,
            "running": False,
            "speed": 1.0,
        },
    )
    for train in migrated.get("trains", []):
        train.setdefault("track", rail_track())
        train.setdefault("stations", [
            {key: value for key, value in station.items() if key != "distance"}
            for station in STATIONS.values()
        ])
    if migrated.get("generation_version") == "poc-9":
        for person in migrated.get("people", []):
            if (person.get("id") == "person:bruno"
                and person.get("workplace_id") in {person.get("home_place_id"), "place:park"}):
                person["workplace_id"] = "place:florist"
                if person.get("activity") == "Working as gardener" and person.get("target_place_id") == person.get("home_place_id"):
                    person["activity"] = "Tending the garden"
                    person["explanation"] = "Gardening at home is a hobby; paid gardening takes place at Fern Florist."
    if migrated.get("generation_version") == "city-10":
        ensure_city_layout(migrated)
    ensure_home_parking(migrated)
    ensure_economy(migrated)
    ensure_prosperity(migrated)
    return migrated
