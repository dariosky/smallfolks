from collections.abc import Iterator

from sqlmodel import Session, create_engine

import settings


engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, **engine_kwargs)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
