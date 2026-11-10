"""Hasła (Argon2) i tokeny JWT.

Moduł jest w shared/, bo weryfikacja JWT jest bezstanowa (wystarczy sekret):
Booking API może w przyszłości sprawdzać token bez dostępu do PostgreSQL.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

log = logging.getLogger(__name__)

_DEV_SECRET = "dev-only-change-me-dev-only-change-me"
JWT_SECRET = os.getenv("JWT_SECRET", _DEV_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

if JWT_SECRET == _DEV_SECRET:
    log.warning("JWT_SECRET not set - using development secret")

# Argon2id - zalecany przez OWASP; pwdlib to następca passlib polecany w dokumentacji FastAPI.
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: int, email: str, is_admin: bool) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "adm": is_admin,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Zwraca payload albo rzuca jwt.InvalidTokenError (zły podpis, wygasły, ...)."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp"]})
