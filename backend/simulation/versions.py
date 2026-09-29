"""Compatibility policy for durable world snapshots."""

from copy import deepcopy
from typing import Any

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
    return migrated
