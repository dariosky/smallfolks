from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class WorldSnapshot(SQLModel, table=True):
    __tablename__ = "world_snapshots"

    id: str = Field(primary_key=True, max_length=80)
    seed: int = Field(index=True)
    world_format_version: int = Field(default=0, nullable=False)
    state_json: str
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
