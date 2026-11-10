"""Modele SQLAlchemy odpowiadające tabelom z db/init.sql.

Źródłem prawdy dla schematu jest db/init.sql; modele tylko go mapują
(nie wywołujemy create_all).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    venue: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128))
    starts_at: Mapped[datetime]
    capacity: Mapped[int]
    available: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    accent: Mapped[str] = mapped_column(String(16), default="coral")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    email: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
