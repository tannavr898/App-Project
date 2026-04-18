import os
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt

from data_store import ensure_database, get_user, upsert_user

SECRET_KEY = os.environ.get("PULSE_SECRET", "pulse-dev-secret-change-in-production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ensure_database()


def register_user(username: str, password: str) -> dict:
    """
    Create a new user. Returns the user dict on success,
    raises ValueError if the username is already taken.
    """
    username = username.strip().lower()
    if not username or len(username) < 2:
        raise ValueError("Username must be at least 2 characters.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    if get_user(username) is not None:
        raise ValueError("Username already taken.")

    upsert_user(
        username=username,
        password_hash=pwd_context.hash(password),
        created_at=datetime.utcnow().isoformat(),
        is_dev=False,
    )
    return {"username": username}


DEV_USERNAME = "dev"
DEV_PASSWORD = "pulse_dev_2026"


def is_dev_account(username: str) -> bool:
    return username.strip().lower() == DEV_USERNAME


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns the user dict on success, None on failure.
    The dev account bypasses normal registration — it always exists.
    """
    username = username.strip().lower()

    # Dev account — hardcoded credentials, never stored
    if username == DEV_USERNAME:
        if password == DEV_PASSWORD:
            return {"username": DEV_USERNAME, "is_dev": True}
        return None

    user = get_user(username)
    if not user:
        return None
    if user.get("is_dev"):
        if password == DEV_PASSWORD:
            return {"username": DEV_USERNAME, "is_dev": True}
        return None
    if not pwd_context.verify(password, user["password_hash"]):
        return None
    return {"username": username, "is_dev": False}


def create_token(username: str) -> str:
    expires = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {"sub": username, "exp": expires}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Returns username if token is valid, None otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None