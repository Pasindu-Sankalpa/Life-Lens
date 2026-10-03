"""SQLite session factory. The file lives under data/ so the schema is inspectable."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "lifelens.db"

_engine = None
SessionLocal: sessionmaker[Session] | None = None


def database_url() -> str:
    override = os.environ.get("LIFELENS_DB")
    if override:
        return override
    DEFAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_PATH}"


def init_db(url: str | None = None) -> None:
    global _engine, SessionLocal
    target = url or database_url()
    if target.startswith("sqlite"):
        DEFAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(target, connect_args={"check_same_thread": False} if target.startswith("sqlite") else {})
    if target.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    _migrate(_engine)
    from app.service import seed

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


def _migrate(engine) -> None:
    """Add audit columns to databases created before calculation versioning."""
    columns = {
        "engine_version": "VARCHAR(16)",
        "knowledge_version": "VARCHAR(32)",
        "input_snapshot": "TEXT",
        "assumption_snapshot": "TEXT",
        "output_snapshot": "TEXT",
    }
    with engine.begin() as connection:
        existing = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(calculations)").fetchall()
        }
        for name, column_type in columns.items():
            if name not in existing:
                connection.exec_driver_sql(f"ALTER TABLE calculations ADD COLUMN {name} {column_type}")


def get_session() -> Iterator[Session]:
    if SessionLocal is None:
        init_db()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
