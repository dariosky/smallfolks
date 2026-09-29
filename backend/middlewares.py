import logging
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import settings

access_logger = logging.getLogger("uvicorn.error")


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _log_access(scope, status_code)


def _log_access(scope: Scope, status_code: int) -> None:
    if not access_logger.isEnabledFor(logging.INFO):
        return
    client = scope.get("client") or ("-", 0)
    client_host, client_port = client
    session = scope.get("session") or {}
    user_id = session.get("user_id") if isinstance(session, dict) else None
    user_suffix = f" user_id={user_id}" if user_id is not None else ""
    access_logger.info(
        '%s:%s - "%s %s HTTP/%s" %s%s',
        client_host,
        client_port,
        scope.get("method", "-"),
        _path_with_query_string(scope),
        scope.get("http_version", "1.1"),
        _status_label(status_code),
        user_suffix,
    )


def _path_with_query_string(scope: Scope) -> str:
    raw_path = scope.get("raw_path")
    path = (
        raw_path.decode("ascii", errors="replace")
        if isinstance(raw_path, bytes)
        else str(scope.get("path") or "")
    )
    query_string = scope.get("query_string", b"")
    if isinstance(query_string, bytes) and query_string:
        return f"{path}?{query_string.decode('ascii', errors='replace')}"
    return path


def _status_label(status_code: int) -> str:
    try:
        return f"{status_code} {HTTPStatus(status_code).phrase}"
    except ValueError:
        return str(status_code)


def get_middlewares() -> list[object]:
    return []


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' https://accounts.google.com https://www.googletagmanager.com 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://accounts.google.com; "
        "frame-src https://accounts.google.com; "
        "connect-src 'self' https://accounts.google.com https://www.google-analytics.com https://region1.google-analytics.com; "
        "img-src 'self' data: https://lh3.googleusercontent.com https://www.google-analytics.com"
    ),
}


def add_middlewares(app: FastAPI) -> None:
    app.add_middleware(AccessLogMiddleware)

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        if "application/json" in response.headers.get("content-type", ""):
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET_KEY,
        same_site="lax",
        https_only=not settings.DEBUG,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in settings.CORS_ORIGINS.split(",")
            if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
