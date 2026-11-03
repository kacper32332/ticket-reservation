import asyncio
import json
import os

from redis.asyncio import Redis


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = "ticket:requests"
EVENTS_KEY = "ticket:events"


async def process_queue() -> None:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    print("ticket worker online")
    try:
        while True:
            item = await redis.blpop(QUEUE_KEY, timeout=5)
            if item is None:
                continue
            _, raw_payload = item
            payload = json.loads(raw_payload)
            await asyncio.sleep(0.05)
            await redis.xadd(EVENTS_KEY, {"type": "ticket_processed", "request_id": payload["id"], "event_id": payload["event_id"]})
            print(f"processed {payload['id']}")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(process_queue())