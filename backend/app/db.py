"""Database session plumbing (SQLAlchemy 2.x).

Defaults to SQLite for zero-config local dev; set DATABASE_URL to a Postgres
DSN (e.g. Supabase) to switch without touching code.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}

engine = create_engine(_settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and seed the emission factor library. Idempotent."""
    from app import models  # noqa: F401  (registers mappers)
    from app.engine.factors import seed_emission_factors

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_emission_factors(db)
