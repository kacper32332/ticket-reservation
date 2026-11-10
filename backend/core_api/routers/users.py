"""Profil użytkownika i historia biletów."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.dependencies import CurrentUser, SessionDep
from shared.database import get_session
from shared.models import Booking
from shared.schemas import BookingOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me/bookings", response_model=list[BookingOut])
async def my_bookings(user: CurrentUser, session: SessionDep):
    """Historia rezerwacji zalogowanego użytkownika.

    Booking API nie zna jeszcze użytkownika (rezerwacje mają tylko e-mail),
    więc dopasowujemy po e-mailu z konta.
    """
    result = await session.scalars(
        select(Booking).where(Booking.email == user.email).order_by(Booking.created_at.desc())
    )
    return list(result)


# Stary wariant bez logowania - zostaje, dopóki frontend nie przejdzie na JWT.
# TODO: usunąć po wdrożeniu logowania we frontendzie (każdy może podejrzeć cudzą historię).
@router.get("/bookings", response_model=list[BookingOut], deprecated=True)
async def list_bookings(email: str, session: AsyncSession = Depends(get_session)):
    result = await session.scalars(
        select(Booking).where(Booking.email == email).order_by(Booking.created_at.desc())
    )
    return list(result)
