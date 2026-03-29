import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_SECRET = os.environ.get(
    "JWT_SECRET",
    "dev-intern-match-change-me-use-32-plus-chars",
)
JWT_ALGO = "HS256"
JWT_EXPIRE_DAYS = 7
AUTH_COOKIE_NAME = "auth_token"
ALLOWED_EMAIL_SUFFIX = "@nottingham.edu.cn"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))


def create_access_token(*, user_id: int, email: str, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "email": email, "username": username, "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


def cookie_secure() -> bool:
    return os.environ.get("AUTH_COOKIE_SECURE", "").lower() in ("1", "true", "yes")
