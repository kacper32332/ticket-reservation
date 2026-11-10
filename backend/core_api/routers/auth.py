"""Rejestracja, logowanie (JWT) i dane bieżącego użytkownika."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from core_api.dependencies import CurrentUser, SessionDep
from shared.database import SessionLocal
from shared.models import User
from shared.schemas import Token, UserCreate, UserOut
from shared.security import create_access_token, hash_password, password_hash, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash "na pusto" - przy nieistniejącym e-mailu i tak liczymy Argon2, żeby czas
# odpowiedzi nie zdradzał, czy konto istnieje (ochrona przed enumeracją kont).
_DUMMY_HASH = password_hash.hash("dummy-password")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: SessionDep):
    user_id = await session.scalar(
        insert(User)
        .values(email=payload.email.lower(), password_hash=hash_password(payload.password))
        .on_conflict_do_nothing(index_elements=[User.email])
        .returning(User.id)
    )
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    await session.commit()
    return await session.get(User, user_id)


@router.post("/login", response_model=Token)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    """Standard OAuth2 password flow: form-data `username` (= e-mail) i `password`."""
    user = await session.scalar(select(User).where(User.email == form.username.lower()))
    if user is None:
        verify_password(form.password, _DUMMY_HASH)
        valid = False
    else:
        valid = verify_password(form.password, user.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id, user.email, user.is_admin))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


async def ensure_admin_account() -> None:
    """Tworzy konto admina z ADMIN_EMAIL / ADMIN_PASSWORD przy starcie Core API.

    Zamiast wpisywać hash do init.sql: hasło nie trafia do repo w postaci hasha
    i można je zmienić zmienną środowiskową (w K8s - Secret). ON CONFLICT DO
    NOTHING sprawia, że kilka replik startujących naraz nie wchodzi sobie w drogę.
    """
    email, password = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if not email or not password:
        return
    async with SessionLocal() as session, session.begin():
        await session.execute(
            insert(User)
            .values(email=email.lower(), password_hash=hash_password(password), is_admin=True)
            .on_conflict_do_nothing(index_elements=[User.email])
        )
