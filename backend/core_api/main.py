"""Core API: odczyt i zarządzanie (PostgreSQL). Skalowane po CPU."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.routers import auth, events, users
from shared.database import engine, get_session
from shared.models import Booking, Event
from shared.redis_client import STREAM_KEY, create_redis
from shared.schemas import Metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis()
    await auth.ensure_admin_account()
    yield
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(title="Ticketline Core API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(users.router)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "unavailable"}


@app.get("/api/metrics", response_model=Metrics)
async def metrics(session: AsyncSession = Depends(get_session)):
    capacity, available = (
        await session.execute(
            select(func.coalesce(func.sum(Event.capacity), 0), func.coalesce(func.sum(Event.available), 0))
        )
    ).one()
    processed = await session.scalar(select(func.count()).select_from(Booking))
    try:
        # Worker usuwa wiadomości (XDEL) dopiero po zapisie w bazie, więc
        # XLEN = czekające w kolejce + aktualnie przetwarzane.
        queue_depth = await app.state.redis.xlen(STREAM_KEY)
    except Exception:
        queue_depth = 0
    return Metrics(
        queue_depth=queue_depth,
        events_processed=processed or 0,
        tickets_sold=capacity - available,
        capacity=capacity,
    )
