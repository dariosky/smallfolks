import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

RATE_LIMIT_DETAIL = "Too many requests. Please try again later."
LOGIN_EMAIL_MAX_ATTEMPTS = 5
LOGIN_EMAIL_WINDOW_SECONDS = 60

limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
    storage_uri="memory://",
)
_login_email_attempts: dict[str, deque[float]] = defaultdict(deque)


def _login_email_key(request: Request, email: str) -> str:
    return f"{get_remote_address(request)}:{email.strip().lower()}"


def require_login_email_rate_limit(request: Request, email: str) -> None:
    now = time.monotonic()
    cutoff = now - LOGIN_EMAIL_WINDOW_SECONDS
    attempts = _login_email_attempts[_login_email_key(request, email)]

    while attempts and attempts[0] <= cutoff:
        attempts.popleft()

    if len(attempts) >= LOGIN_EMAIL_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_DETAIL,
        )

    attempts.append(now)


def rate_limit_exceeded_handler(request: Request, _: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        {"detail": RATE_LIMIT_DETAIL},
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    if view_rate_limit is not None:
        return request.app.state.limiter._inject_headers(response, view_rate_limit)
    return response


def reset_rate_limits() -> None:
    limiter.reset()
    _login_email_attempts.clear()
