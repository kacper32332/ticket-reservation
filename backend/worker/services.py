"""Logika biznesowa rezerwacji: dostępność miejsc i zapis do PostgreSQL."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from shared.database import SessionLocal
from shared.models import Booking, Event
from shared.schemas import QueuedBooking


class _Duplicate(Exception):
    """To żądanie zostało już przetworzone."""


@dataclass
class BookingResult:
    status: str  # "confirmed" | "rejected"
    reason: Optional[str] = None


async def book_tickets(message: QueuedBooking) -> BookingResult:
    """Rezerwuje miejsca w jednej transakcji.

    Zamiast SELECT ... FOR UPDATE używamy jednego atomowego UPDATE z warunkiem
    available >= quantity: blokada wiersza wydarzenia trwa tylko na czas tego
    zapytania, a overbooking jest niemożliwy.

    Idempotencja: bookings.request_id jest UNIQUE. Jeśli to samo żądanie trafi
    do workera drugi raz, INSERT nic nie wstawi, transakcja zostanie wycofana
    (razem ze zmniejszeniem licznika) i zwrócimy wynik zapisany za pierwszym razem.
    """
    try:
        async with SessionLocal() as session, session.begin():
            remaining = await session.scalar(
                update(Event)
                .where(Event.id == message.event_id, Event.available >= message.quantity)
                .values(available=Event.available - message.quantity)
                .returning(Event.available)
            )

            if remaining is None:
                if await session.get(Event, message.event_id) is None:
                    # Nie ma czego zapisać w bookings (klucz obcy) - tylko status w Redisie.
                    return BookingResult("rejected", "event_not_found")
                status, reason = "rejected", "sold_out"
            else:
                status, reason = "confirmed", None

            inserted_id = await session.scalar(
                insert(Booking)
                .values(
                    request_id=message.request_id,
                    event_id=message.event_id,
                    email=message.email,
                    quantity=message.quantity,
                    status=status,
                )
                .on_conflict_do_nothing(index_elements=[Booking.request_id])
                .returning(Booking.id)
            )
            if inserted_id is not None:
                return BookingResult(status, reason)  # wyjście z bloku = COMMIT
            raise _Duplicate  # wyjście wyjątkiem = ROLLBACK
    except _Duplicate:
        pass

    # Duplikat: zwróć wynik pierwszego przetworzenia.
    async with SessionLocal() as session:
        previous = await session.scalar(
            select(Booking.status).where(Booking.request_id == message.request_id)
        )
        return BookingResult(previous or "rejected", "duplicate")
