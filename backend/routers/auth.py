import re
from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import (
    AUTH_COOKIE_NAME,
    ALLOWED_EMAIL_SUFFIX,
    cookie_secure,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from db.database import get_db
from db.models import User

router = APIRouter(prefix="/auth", tags=["认证"])

_username_re = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff]{2,32}$")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _attach_auth_cookie(response: Response, token: str) -> None:
    max_age = 7 * 24 * 60 * 60
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.cookies.get(AUTH_COOKIE_NAME)


class RegisterBody(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    privacy_consent: bool = False

    @field_validator("email")
    @classmethod
    def email_domain(cls, v: str) -> str:
        e = _normalize_email(v)
        if not e.endswith(ALLOWED_EMAIL_SUFFIX):
            raise ValueError("请使用宁波诺丁汉大学邮箱（@nottingham.edu.cn）注册")
        return e

    @field_validator("username")
    @classmethod
    def username_fmt(cls, v: str) -> str:
        s = v.strip()
        if not _username_re.match(s):
            raise ValueError("用户名为 2–32 位，仅含字母、数字、下划线或中文")
        return s


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def email_norm(cls, v: str) -> str:
        return _normalize_email(v)


class UserOut(BaseModel):
    id: int
    email: str
    username: str

    model_config = {"from_attributes": True}


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    uid = int(payload["sub"])
    user = db.scalar(select(User).where(User.id == uid))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


@router.post("/register")
def register(
    body: RegisterBody,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    if not body.privacy_consent:
        raise HTTPException(status_code=400, detail="请阅读并同意隐私政策与用户条款")

    user = User(
        email=body.email,
        username=body.username.strip(),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该邮箱或用户名已被注册")

    token = create_access_token(user_id=user.id, email=user.email, username=user.username)
    _attach_auth_cookie(response, token)
    return {"user": UserOut.model_validate(user)}


@router.post("/login")
def login(
    body: LoginBody,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(user_id=user.id, email=user.email, username=user.username)
    _attach_auth_cookie(response, token)
    return {"user": UserOut.model_validate(user)}


@router.get("/me")
def me(user: Annotated[User, Depends(get_current_user)]):
    return {"user": UserOut.model_validate(user)}


@router.post("/logout")
def logout(response: Response):
    _clear_auth_cookie(response)
    return {"ok": True}
