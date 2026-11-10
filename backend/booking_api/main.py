"""Booking API: odchudzony producent. Przyjmuje rezerwację, wkłada ją do Redisa
i natychmiast zwraca 202 Accepted. Skalowane agresywnie (HPA)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from booking_api.producer import enqueue_booking
from shared.redis_client import create_redis, status_key
from shared.schemas import TicketRequest, TicketRequestStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis()
    yield
    await app.state.redis.aclose()


app = FastAPI(title="Ticketline Booking API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health(request: Request):
    try:
        await request.app.state.redis.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception:
        return {"status": "degraded", "redis": "unavailable"}


@app.post("/api/ticket-requests", status_code=202)
async def request_ticket(ticket: TicketRequest, request: Request):
    try:
        request_id, position = await enqueue_booking(request.app.state.redis, ticket)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Ticket queue is unavailable") from error
    return {"request_id": request_id, "status": "queued", "position": position}


@app.get("/api/ticket-requests/{request_id}", response_model=TicketRequestStatus)
async def ticket_request_status(request_id: str, request: Request):
    data = await request.app.state.redis.hgetall(status_key(request_id))
    if not data:
        raise HTTPException(status_code=404, detail="Unknown or expired request")
    return TicketRequestStatus(request_id=request_id, status=data["status"], reason=data.get("reason"))
