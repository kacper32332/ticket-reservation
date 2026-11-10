"""Wspólna konfiguracja połączenia z PostgreSQL (SQLAlchemy 2.0, async)."""

import os
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://tickets:tickets@localhost:5432/tickets",
)

# Rozmiar puli jest konfigurowalny, bo przy autoskalowaniu
# (liczba podów x pool_size) łatwo przekroczyć max_connections Postgresa.
engine = create_async_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    # Wszystkie kolumny datetime to TIMESTAMPTZ (jak w db/init.sql).
    type_annotation_map = {datetime: DateTime(timezone=True)}


async def get_session() -> AsyncIterator[AsyncSession]:
    """Zależność FastAPI: jedna sesja na żądanie."""
    async with SessionLocal() as session:
        yield session
