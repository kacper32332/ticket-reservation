"""Background Worker (konsument). Czyta żądania z Redis Streams i zapisuje je w PostgreSQL.

Gwarancje dostarczania (at-least-once + idempotentny konsument):
  1. XREADGROUP ">"  - nowe wiadomości trafiają do PEL (Pending Entries List)
     tego konsumenta; dopóki nie ma XACK, Redis pamięta, że są "w trakcie".
  2. COMMIT w PostgreSQL, zapis statusu w Redisie, dopiero potem XACK + XDEL.
     Pad workera przed XACK = wiadomość zostaje w PEL, nic nie ginie.
  3. XAUTOCLAIM      - co CLAIM_INTERVAL s worker przejmuje wiadomości, które
     wiszą w PEL dłużej niż CLAIM_IDLE_MS (osierocone po padzie innego poda).
  4. Ponowne przetworzenie jest bezpieczne: bookings.request_id jest UNIQUE.
  5. Wiadomości, których nie da się przetworzyć (zły format albo więcej niż
     MAX_DELIVERIES prób), trafiają do strumienia ticket:dead (dead letter).

Graceful shutdown: SIGTERM (scale-down w K8s / KEDA, docker compose stop)
kończy bieżącą paczkę, nie pobiera nowych wiadomości i wyrejestrowuje
konsumenta z grupy, jeśli nie ma już nic w swoim PEL.
"""

import asyncio
import logging
import os
import signal
import socket
import time

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from shared.database import engine
from shared.redis_client import (
    CONSUMER_GROUP,
    DEAD_LETTER_KEY,
    STREAM_FIELD,
    STREAM_KEY,
    create_redis,
    ensure_consumer_group,
)
from shared.schemas import QueuedBooking
from worker.services import BookingResult
from worker.tasks import process_booking, save_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

# Nazwa konsumenta musi być unikalna w grupie i stabilna po restarcie procesu:
# w kontenerze/podzie hostname = id kontenera / nazwa poda.
CONSUMER_NAME = os.getenv("WORKER_NAME") or socket.gethostname()
# Ile wiadomości naraz (= ile równoległych transakcji). Nie więcej niż pula
# połączeń do bazy (DB_POOL_SIZE + DB_MAX_OVERFLOW), inaczej zadania czekają na pulę.
BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "10"))
BLOCK_MS = int(os.getenv("WORKER_BLOCK_MS", "1000"))
CLAIM_IDLE_MS = int(os.getenv("WORKER_CLAIM_IDLE_MS", "30000"))
CLAIM_INTERVAL = float(os.getenv("WORKER_CLAIM_INTERVAL", "10"))
MAX_DELIVERIES = int(os.getenv("WORKER_MAX_DELIVERIES", "5"))

Message = tuple[str, dict[str, str] | None]


async def acknowledge(redis: Redis, message_id: str) -> None:
    """XACK zdejmuje wiadomość z PEL, XDEL usuwa ją ze strumienia.

    XDEL zamiast MAXLEN przy XADD: usuwamy tylko to, co na pewno zapisano
    w bazie, więc XLEN = wiadomości czekające + w trakcie przetwarzania.
    Usuwamy wyłącznie wpisy już dostarczone grupie, więc licznik "lag"
    (używany przez skaler KEDA redis-streams) pozostaje poprawny.
    """
    async with redis.pipeline(transaction=True) as pipe:
        pipe.xack(STREAM_KEY, CONSUMER_GROUP, message_id)
        pipe.xdel(STREAM_KEY, message_id)
        await pipe.execute()


async def dead_letter(redis: Redis, message_id: str, fields: dict[str, str], error: str) -> None:
    """Przenosi wiadomość do ticket:dead i oznacza żądanie jako odrzucone."""
    log.error("dead letter %s: %s %s", message_id, error, fields)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.xadd(DEAD_LETTER_KEY, {**fields, "source_id": message_id, "error": error})
        pipe.xack(STREAM_KEY, CONSUMER_GROUP, message_id)
        pipe.xdel(STREAM_KEY, message_id)
        await pipe.execute()
    try:
        message = QueuedBooking.model_validate_json(fields.get(STREAM_FIELD, ""))
    except ValidationError:
        return  # bez request_id nie ma czego zaktualizować
    await save_status(redis, message.request_id, BookingResult("rejected", "processing_failed"))


async def handle(redis: Redis, message_id: str, fields: dict[str, str] | None) -> None:
    if not fields:
        # Wpis usunięty ze strumienia, a wciąż w PEL - tylko sprzątamy.
        await redis.xack(STREAM_KEY, CONSUMER_GROUP, message_id)
        return
    try:
        message = QueuedBooking.model_validate_json(fields.get(STREAM_FIELD, ""))
    except ValidationError:
        await dead_letter(redis, message_id, fields, "invalid_message")
        return
    await process_booking(redis, message)
    await acknowledge(redis, message_id)  # dopiero po COMMIT


async def process_batch(redis: Redis, messages: list[Message]) -> None:
    results = await asyncio.gather(
        *(handle(redis, message_id, fields) for message_id, fields in messages),
        return_exceptions=True,
    )
    for (message_id, _), result in zip(messages, results):
        if isinstance(result, Exception):
            # Bez XACK: wiadomość zostaje w PEL i wróci przez XAUTOCLAIM.
            log.error("failed to process %s: %r", message_id, result)


async def drain_own_pending(redis: Redis) -> None:
    """Po restarcie z tą samą nazwą: dokończ wiadomości z własnego PEL.

    Odczyt z id innym niż ">" zwraca historię PEL tego konsumenta od podanego id.
    Przesuwamy kursor, więc wiadomości, które znowu się nie udały, nie kręcą się
    w kółko - zostają w PEL i przejmie je później XAUTOCLAIM (z limitem prób).
    """
    cursor = "0"
    while True:
        response = await redis.xreadgroup(
            CONSUMER_GROUP, CONSUMER_NAME, {STREAM_KEY: cursor}, count=BATCH_SIZE
        )
        messages = response[0][1] if response else []
        if not messages:
            return
        log.info("recovering %d own pending messages", len(messages))
        await process_batch(redis, messages)
        cursor = messages[-1][0]


async def reclaim_orphans(redis: Redis) -> None:
    """XAUTOCLAIM: przejmij wiadomości osierocone przez martwych konsumentów."""
    start = "0-0"
    while True:
        next_start, messages, *_ = await redis.xautoclaim(
            STREAM_KEY, CONSUMER_GROUP, CONSUMER_NAME,
            min_idle_time=CLAIM_IDLE_MS, start_id=start, count=BATCH_SIZE,
        )
        if messages:
            log.warning("claimed %d orphaned messages", len(messages))
            to_process: list[Message] = []
            for message_id, fields in messages:
                info = await redis.xpending_range(
                    STREAM_KEY, CONSUMER_GROUP, min=message_id, max=message_id, count=1
                )
                deliveries = info[0]["times_delivered"] if info else 0
                if fields and deliveries > MAX_DELIVERIES:
                    await dead_letter(redis, message_id, fields, f"max_deliveries:{deliveries}")
                else:
                    to_process.append((message_id, fields))
            await process_batch(redis, to_process)
        if next_start in ("0-0", start):
            return
        start = next_start


async def unregister_if_idle(redis: Redis) -> None:
    """Przy wyłączaniu: usuń konsumenta z grupy, jeśli nic po nim nie zostało."""
    pending = await redis.xpending_range(
        STREAM_KEY, CONSUMER_GROUP, min="-", max="+", count=1, consumername=CONSUMER_NAME
    )
    if pending:
        log.warning("leaving %s with pending messages - XAUTOCLAIM will take over", CONSUMER_NAME)
    else:
        await redis.xgroup_delconsumer(STREAM_KEY, CONSUMER_GROUP, CONSUMER_NAME)


async def run() -> None:
    redis = create_redis()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows bez Dockera
            pass

    await ensure_consumer_group(redis)
    log.info("ticket worker %s online (group=%s, batch=%d)", CONSUMER_NAME, CONSUMER_GROUP, BATCH_SIZE)
    next_claim = 0.0
    try:
        await drain_own_pending(redis)
        while not stop.is_set():
            try:
                if time.monotonic() >= next_claim:
                    await reclaim_orphans(redis)
                    next_claim = time.monotonic() + CLAIM_INTERVAL
                response = await redis.xreadgroup(
                    CONSUMER_GROUP, CONSUMER_NAME, {STREAM_KEY: ">"},
                    count=BATCH_SIZE, block=BLOCK_MS,
                )
                for _stream, messages in response or []:
                    await process_batch(redis, messages)
            except ResponseError as error:
                if "NOGROUP" in str(error):
                    # Strumień/grupa zniknęły (np. FLUSHALL) - odtwarzamy.
                    await ensure_consumer_group(redis)
                else:
                    raise
            except (RedisConnectionError, RedisTimeoutError) as error:
                log.error("redis unavailable: %r - retrying", error)
                await asyncio.sleep(1)
        log.info("SIGTERM received - finishing")
        await unregister_if_idle(redis)
    finally:
        await redis.aclose()
        await engine.dispose()
        log.info("ticket worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
