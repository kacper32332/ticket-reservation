"""Schematy Pydantic współdzielone przez serwisy."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Rezerwacje (Booking API -> kolejka -> Worker) ---

class TicketRequest(BaseModel):
    """Body POST /api/ticket-requests."""

    event_id: str
    quantity: int = Field(default=1, ge=1, le=8)
    email: str
    # Klucz idempotencji generowany przez klienta; jeśli go brak, nada go Booking API.
    request_id: Optional[str] = Field(default=None, max_length=64)


class QueuedBooking(BaseModel):
    """Wiadomość wkładana do kolejki w Redisie."""

    request_id: str
    event_id: str
    quantity: int
    email: str
    created_at: datetime


BookingStatus = Literal["queued", "confirmed", "rejected"]


class TicketRequestStatus(BaseModel):
    request_id: str
    status: BookingStatus
    reason: Optional[str] = None


# --- Użytkownicy i logowanie (Core API) ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_admin: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


# --- Wydarzenia (Core API) ---

class EventCreate(BaseModel):
    id: str = Field(max_length=32)
    name: str
    venue: str
    city: str
    starts_at: datetime
    capacity: int = Field(gt=0)
    price: float = Field(ge=0)
    accent: str = "coral"


class EventOut(BaseModel):
    """Kształt zgodny z tym, czego oczekuje frontend."""

    id: str
    name: str
    venue: str
    city: str
    date: str
    starts_at: datetime
    status: str
    sold: int
    capacity: int
    available: int
    price: float
    accent: str


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    event_id: str
    quantity: int
    status: str
    created_at: datetime


class Metrics(BaseModel):
    queue_depth: int
    events_processed: int
    tickets_sold: int
    capacity: int
