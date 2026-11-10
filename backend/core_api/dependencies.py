"""Zależności FastAPI: bieżący użytkownik z tokenu JWT i wymaganie roli admina."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_session
from shared.models import User
from shared.security import decode_access_token

# tokenUrl = endpoint logowania; dzięki temu działa przycisk "Authorize" w Swaggerze.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized
    # Core API i tak ma dostęp do bazy: sprawdzamy, czy konto nadal istnieje
    # i czy rola się nie zmieniła (sam token mógł zostać wydany wcześniej).
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
