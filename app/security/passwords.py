"""Password hashing utilities backed by Passlib (Argon2)."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a secure hash for ``password`` using Argon2."""

    if not password:
        raise ValueError("Password must be non-empty.")
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Validate ``password`` against ``hashed_password``."""

    if not hashed_password:
        return False
    return _pwd_context.verify(password, hashed_password)


__all__ = ["hash_password", "verify_password"]
