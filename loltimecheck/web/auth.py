from __future__ import annotations

import time
from typing import Annotated

import jwt
from fastapi import Cookie, Header, HTTPException, Response, status
from jwt import InvalidTokenError

from loltimecheck.core.config import AppConfig


def create_token(config: AppConfig, *, subject: str = "admin", ttl_seconds: int = 60 * 60 * 12) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": subject, "iat": now, "exp": now + ttl_seconds},
        config.jwt_secret,
        algorithm="HS256",
    )


def verify_token(config: AppConfig, token: str) -> dict:
    try:
        return jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc


def set_session_cookie(response: Response, config: AppConfig, token: str) -> None:
    response.set_cookie(
        config.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
        path="/",
    )


def clear_session_cookie(response: Response, config: AppConfig) -> None:
    response.delete_cookie(config.session_cookie_name, path="/")


def require_configured_auth(config: AppConfig) -> None:
    if not config.admin_password or not config.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_PASSWORD and JWT_SECRET must be configured.",
        )


def auth_dependency(config: AppConfig):
    def require_auth(
        authorization: Annotated[str | None, Header()] = None,
        session: Annotated[str | None, Cookie(alias=config.session_cookie_name)] = None,
    ) -> dict:
        require_configured_auth(config)
        token = session
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return verify_token(config, token)

    return require_auth
