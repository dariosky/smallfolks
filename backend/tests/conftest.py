import sys
from pathlib import Path

from sqlmodel import SQLModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import persistence.models  # noqa: F401
from db import engine


def pytest_sessionstart() -> None:
    SQLModel.metadata.create_all(engine)
