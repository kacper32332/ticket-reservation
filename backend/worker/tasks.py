"""Zadania wykonywane przez workera."""

import logging

from redis.asyncio import Redis

from shared.redis_client import STATUS_TTL_SECONDS, status_key
from shared.schemas import QueuedBooking
from worker.services import BookingResult, book_tickets

log = logging.getLogger("worker")


async def save_status(redis: Redis, request_id: str, result: BookingResult) -> None:
    mapping = {"status": result.status}
    if result.reason:
        mapping["reason"] = result.reason
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(status_key(request_id), mapping=mapping)
        pipe.expire(status_key(request_id), STATUS_TTL_SECONDS)
        await pipe.execute()


async def process_booking(redis: Redis, message: QueuedBooking) -> BookingResult:
    """Zapis w PostgreSQL + status w Redisie.

    Wyjątek (np. baza niedostępna) propaguje się do pętli workera - wiadomość
    NIE zostaje potwierdzona (XACK) i wróci do przetworzenia przez XAUTOCLAIM.
    Ponowne przetworzenie jest bezpieczne dzięki idempotencji po request_id.
    """
    result = await book_tickets(message)
    await save_status(redis, message.request_id, result)
    log.info("%s %s event=%s qty=%s %s", message.request_id, result.status,
             message.event_id, message.quantity, result.reason or "")
    return result
