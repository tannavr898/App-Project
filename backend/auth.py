import json
import os
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt

SECRET_KEY = os.environ.get("PULSE_SECRET", "pulse-dev-secret-change-in-production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS_FILE = "users/auth.json"


def _load_auth() -> dict:
    os.makedirs("users", exist_ok=True)
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_auth(data: dict):
    os.makedirs("users", exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


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

    auth = _load_auth()
    if username in auth:
        raise ValueError("Username already taken.")

    auth[username] = {
        "username":      username,
        "password_hash": pwd_context.hash(password),
        "created_at":    datetime.utcnow().isoformat(),
    }
    _save_auth(auth)
    return {"username": username}


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns the user dict on success, None on failure.
    """
    username = username.strip().lower()
    auth = _load_auth()
    user = auth.get(username)
    if not user:
        return None
    if not pwd_context.verify(password, user["password_hash"]):
        return None
    return {"username": username}


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