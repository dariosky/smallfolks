import os
import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_PATH = Path(tempfile.mkstemp(prefix="smallfolk-tests-", suffix=".db")[1])

# This must happen before importing settings/db. Tests must never use backend/.env.
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH}"
os.environ["TESTING_MODE"] = "true"
os.environ["ENABLE_HTML_SERVING"] = "true"
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

sys.path.insert(0, str(BACKEND_DIR))

from sqlmodel import SQLModel  # noqa: E402

import persistence.models  # noqa: E402,F401
from db import engine  # noqa: E402


def pytest_sessionstart() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")


def pytest_sessionfinish() -> None:
    TEST_DATABASE_PATH.unlink(missing_ok=True)


def pytest_runtest_setup() -> None:
    with engine.begin() as connection:
        for table in reversed(SQLModel.metadata.sorted_tables):
            connection.execute(delete(table))
