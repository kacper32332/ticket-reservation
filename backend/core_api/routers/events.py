"""Przeglądanie oferty i dodawanie wydarzeń."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.dependencies import AdminUser
from shared.database import get_session
from shared.models import Event
from shared.schemas import EventCreate, EventOut

router = APIRouter(prefix="/api/events", tags=["events"])

LOW_STOCK_RATIO = 0.15


def to_out(event: Event) -> EventOut:
    if event.available == 0:
        label = "Sold out"
    elif event.available / event.capacity < LOW_STOCK_RATIO:
        label = "Low stock"
    else:
        label = "On sale"
    return EventOut(
        id=event.id,
        name=event.name,
        venue=event.venue,
        city=event.city,
        date=event.starts_at.strftime("%d %b %Y"),
        starts_at=event.starts_at,
        status=label,
        sold=event.capacity - event.available,
        capacity=event.capacity,
        available=event.available,
        price=float(event.price),
        accent=event.accent,
    )


@router.get("", response_model=list[EventOut])
async def list_events(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(select(Event).order_by(Event.starts_at))
    return [to_out(event) for event in result]


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: str, session: AsyncSession = Depends(get_session)):
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return to_out(event)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    _admin: AdminUser,  # 401 bez tokenu, 403 dla zwykłego użytkownika
    session: AsyncSession = Depends(get_session),
):
    if await session.get(Event, payload.id) is not None:
        raise HTTPException(status_code=409, detail="Event already exists")
    event = Event(**payload.model_dump(), available=payload.capacity)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return to_out(event)
