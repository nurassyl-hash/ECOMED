"""Инициализация БД и сессий (SQLite через SQLAlchemy).

Данные хранятся вне session_state Streamlit и переживают перезапуск (ТЗ FR-01).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ecomed.config import settings
from ecomed.db.models import Base

_engine: Engine = create_engine(
    settings.db_url,
    future=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(_engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _):
    """Включаем проверку внешних ключей и CHECK-ограничений в SQLite."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(_engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
