from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from aegisops_api.config import Settings, get_settings


def get_database_url(settings: Settings | None = None) -> str:
    resolved_settings = settings or get_settings()
    if resolved_settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required for database access")
    return resolved_settings.database_url


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    resolved_url = database_url or get_database_url()
    return create_engine(resolved_url, pool_pre_ping=True)


@lru_cache
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(database_url),
        autoflush=False,
        expire_on_commit=False,
    )


def get_session(database_url: str | None = None) -> Generator[Session, None, None]:
    session = get_session_factory(database_url)()
    try:
        yield session
    finally:
        session.close()
