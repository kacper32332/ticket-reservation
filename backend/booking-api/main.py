import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis.asyncio import Redis


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = "ticket:requests"
EVENTS_KEY = "ticket:events"


class TicketRequest(BaseModel):
    event_id: str
    quantity: int = Field(default=1, ge=1, le=8)
    email: str


class Event(BaseModel):
    id: str
    name: str
    venue: str
    date: str
    city: str
    status: str
    sold: int
    capacity: int
    price: int
    accent: str


EVENTS = [
    Event(id="evt-001", name="The Weeknd", venue="National Stadium", date="24 Oct 2026", city="Warsaw", status="On sale", sold=18420, capacity=30000, price=89, accent="coral"),
    Event(id="evt-002", name="Open'er Festival", venue="Gdynia-Kosakowo Airport", date="1–4 Jul 2026", city="Gdynia", status="On sale", sold=41600, capacity=60000, price=149, accent="mint"),
    Event(id="evt-003", name="Formula E Berlin", venue="Tempelhof Circuit", date="12 Sep 2026", city="Berlin", status="Low stock", sold=19750, capacity=22000, price=119, accent="yellow"),
]


redis: Optional[Redis] = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global redis
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    yield
    await redis.aclose()


app = FastAPI(title="Ticketline Booking API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    try:
        assert redis is not None
        await redis.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception:
        return {"status": "degraded", "redis": "unavailable"}


@app.get("/api/events", response_model=list[Event])
async def get_events():
    return EVENTS


@app.post("/api/ticket-requests", status_code=202)
async def request_ticket(ticket: TicketRequest):
    event = next((item for item in EVENTS if item.id == ticket.event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    request_id = f"req-{uuid4().hex[:10]}"
    payload = {
        "id": request_id,
        "event_id": ticket.event_id,
        "quantity": ticket.quantity,
        "email": ticket.email,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        assert redis is not None
        await redis.rpush(QUEUE_KEY, json.dumps(payload))
        await redis.xadd(EVENTS_KEY, {"type": "ticket_requested", "request_id": request_id, "event_id": ticket.event_id})
    except Exception as error:
        raise HTTPException(status_code=503, detail="Ticket queue is unavailable") from error
    return {"request_id": request_id, "status": "queued", "position": await redis.llen(QUEUE_KEY)}


@app.get("/api/metrics")
async def metrics():
    queue_depth = 0
    stream_length = 0
    try:
        assert redis is not None
        queue_depth = await redis.llen(QUEUE_KEY)
        stream_length = await redis.xlen(EVENTS_KEY)
    except Exception:
        pass
    total_capacity = sum(event.capacity for event in EVENTS)
    sold = sum(event.sold for event in EVENTS)
    return {"queue_depth": queue_depth, "events_processed": stream_length, "tickets_sold": sold, "capacity": total_capacity}