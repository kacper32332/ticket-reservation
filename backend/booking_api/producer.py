"""Tworzenie zadań rezerwacji i wysyłanie ich do Redisa.

Booking API nigdy nie odpytuje PostgreSQL: istnienie wydarzenia
i dostępność miejsc sprawdza dopiero Worker.
"""

from datetime import datetime, timezone
from uuid import uuid4

from redis.asyncio import Redis

from shared.redis_client import STATUS_TTL_SECONDS, STREAM_FIELD, STREAM_KEY, status_key
from shared.schemas import QueuedBooking, TicketRequest


async def enqueue_booking(redis: Redis, ticket: TicketRequest) -> tuple[str, int]:
    """Dodaje żądanie do strumienia. Zwraca (request_id, długość strumienia)."""
    request_id = ticket.request_id or f"req-{uuid4().hex}"
    message = QueuedBooking(
        request_id=request_id,
        event_id=ticket.event_id,
        quantity=ticket.quantity,
        email=ticket.email,
        created_at=datetime.now(timezone.utc),
    )
    # Jedna transakcja MULTI/EXEC = jedno okrążenie do Redisa. Status "queued"
    # i wiadomość pojawiają się atomowo, więc klient nigdy nie zobaczy 404
    # dla żądania, które już jest w kolejce.
    # Celowo BEZ MAXLEN: przycinanie strumienia mogłoby usunąć nieprzetworzone
    # wiadomości. Strumień czyści worker (XACK + XDEL po zapisie do bazy).
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(status_key(request_id), mapping={"status": "queued"})
        pipe.expire(status_key(request_id), STATUS_TTL_SECONDS)
        pipe.xadd(STREAM_KEY, {STREAM_FIELD: message.model_dump_json()})
        pipe.xlen(STREAM_KEY)
        *_, stream_length = await pipe.execute()
    return request_id, stream_length
