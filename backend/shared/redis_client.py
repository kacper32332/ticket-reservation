"""Wspólna konfiguracja Redisa, nazwy kluczy i obsługa strumienia (Redis Streams)."""

import os

from redis.asyncio import Redis
from redis.exceptions import ResponseError

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Kolejka żądań rezerwacji: Redis Stream + consumer group.
# Booking API robi XADD, workery czytają przez XREADGROUP i potwierdzają XACK
# dopiero po COMMIT w PostgreSQL (dostarczanie at-least-once).
STREAM_KEY = "ticket:stream"
CONSUMER_GROUP = "booking-workers"
# Pole wiadomości w strumieniu, w którym trzymamy JSON z QueuedBooking.
STREAM_FIELD = "data"
# Wiadomości, których nie da się przetworzyć (zły format, zbyt wiele prób).
DEAD_LETTER_KEY = "ticket:dead"

# Status pojedynczego żądania: hash pod kluczem booking:{request_id}.
STATUS_KEY_PREFIX = "booking:"
STATUS_TTL_SECONDS = 60 * 60


def status_key(request_id: str) -> str:
    return f"{STATUS_KEY_PREFIX}{request_id}"


def create_redis() -> Redis:
    return Redis.from_url(REDIS_URL, decode_responses=True)


async def ensure_consumer_group(redis: Redis) -> None:
    """Tworzy consumer group (i strumień, jeśli go nie ma).

    Start od id "0", a nie "$": wiadomości dodane przez Booking API zanim
    wystartował pierwszy worker też zostaną przetworzone. Wywołanie jest
    idempotentne - wiele workerów startujących naraz dostanie BUSYGROUP.
    """
    try:
        await redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise
