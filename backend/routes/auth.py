import json
import logging
import secrets
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlmodel import Session, select

import settings
from db import get_session
from models.auth import User
from rate_limits import (
    get_remote_address,
    limiter,
    require_login_email_rate_limit,
)
from routes.deps import get_current_user
from services.auth import (
    EMAIL_PURPOSE_MAGIC_LOGIN,
    EMAIL_PURPOSE_PASSWORD_RESET,
    EMAIL_PURPOSE_VERIFICATION,
    build_magic_login_expires_at,
    build_magic_login_url,
    build_password_reset_expires_at,
    build_password_reset_url,
    get_auth_email_retry_after_seconds,
    hash_password,
    record_auth_email_send,
    verify_email_verification_code,
    verify_magic_login_code,
    verify_password,
    verify_password_reset_code,
)
from services.mail import (
    send_account_exists_email,
    send_magic_login_email,
    send_password_reset_email,
    send_verification_email,
)

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)
GOOGLE_SIGN_IN_FAILED_DETAIL = (
    "Google sign-in failed. Please try another sign-in method."
)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    email_validated: bool
    is_admin: bool
    full_name: str
    profile_picture_url: str | None = None


class VerificationResponse(BaseModel):
    detail: str


class GoogleConfigResponse(BaseModel):
    client_id: str | None


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=255)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_required_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required.")
        return stripped


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


class UpdateUserRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_required_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required.")
        return stripped


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=1, max_length=512)


class MagicLoginRequest(BaseModel):
    email: EmailStr


class MagicLoginConsumeRequest(BaseModel):
    email: EmailStr
    expires: int
    code: str = Field(min_length=64, max_length=64)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConsumeRequest(BaseModel):
    email: EmailStr
    expires: int
    code: str = Field(min_length=64, max_length=64)
    password: str = Field(min_length=8, max_length=255)


class GoogleOneTapRequest(BaseModel):
    credential: str = Field(min_length=1)


class GoogleProfile(BaseModel):
    sub: str
    email: EmailStr
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None


class GoogleCredentialConfigurationError(RuntimeError):
    pass


def store_user_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["session_version"] = user.session_version
    request.state.user_id = user.id


def require_auth_email_cooldown(
    session: Session, *, email: str, purpose: str, cooldown_seconds: int
) -> None:
    retry_after = get_auth_email_retry_after_seconds(
        session,
        email=email,
        purpose=purpose,
        cooldown_seconds=cooldown_seconds,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {retry_after} seconds before requesting another email.",
        )


REGISTER_SUCCESS_MESSAGE = (
    "Your account is being set up. Check your inbox to verify your email."
)
PASSWORD_RESET_REQUEST_MESSAGE = (  # nosec: B105
    "If that email has a SmallFolks account, we sent a password reset link."
)
MAGIC_LOGIN_REQUEST_MESSAGE = (  # nosec: B105
    "If that email has a SmallFolks account, we sent a sign-in link."
)


@router.get("/google/config", response_model=GoogleConfigResponse)
def google_config() -> GoogleConfigResponse:
    client_id = settings.GOOGLE_CLIENT_ID.strip() or None
    return GoogleConfigResponse(client_id=client_id)


@router.post("/register", response_model=VerificationResponse)
@limiter.limit("3/hour")
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> VerificationResponse:
    normalized_email = payload.email.lower()
    existing_user = session.exec(
        select(User).where(User.email == normalized_email)
    ).one_or_none()
    if existing_user:
        require_auth_email_cooldown(
            session,
            email=normalized_email,
            purpose=EMAIL_PURPOSE_VERIFICATION,
            cooldown_seconds=settings.EMAIL_VERIFICATION_COOLDOWN_SECONDS,
        )
        record_auth_email_send(
            session, email=normalized_email, purpose=EMAIL_PURPOSE_VERIFICATION
        )
        session.commit()
        send_account_exists_email(
            recipient_email=existing_user.email,
            full_name=existing_user.full_name,
        )
        return VerificationResponse(detail=REGISTER_SUCCESS_MESSAGE)

    require_auth_email_cooldown(
        session,
        email=normalized_email,
        purpose=EMAIL_PURPOSE_VERIFICATION,
        cooldown_seconds=settings.EMAIL_VERIFICATION_COOLDOWN_SECONDS,
    )
    user = User(
        email=normalized_email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.flush()
    record_auth_email_send(
        session, email=user.email, purpose=EMAIL_PURPOSE_VERIFICATION
    )
    send_verification_email(recipient_email=user.email, full_name=user.full_name)
    session.commit()
    session.refresh(user)
    store_user_session(request, user)
    return VerificationResponse(detail=REGISTER_SUCCESS_MESSAGE)


@router.post("/login", response_model=UserResponse)
@limiter.limit("5/minute")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> UserResponse:
    require_login_email_rate_limit(request, payload.email)
    user = session.exec(
        select(User).where(User.email == payload.email.lower())
    ).one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    store_user_session(request, user)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.state.user_id = request.session.get("user_id")
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserResponse:
    current_user.full_name = payload.full_name
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/send-verification-email", response_model=VerificationResponse)
@limiter.limit("3/hour", key_func=get_remote_address)
def resend_verification_email(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> VerificationResponse:
    if current_user.email_validated:
        return VerificationResponse(detail="Your email is already verified.")
    require_auth_email_cooldown(
        session,
        email=current_user.email,
        purpose=EMAIL_PURPOSE_VERIFICATION,
        cooldown_seconds=settings.EMAIL_VERIFICATION_COOLDOWN_SECONDS,
    )
    record_auth_email_send(
        session, email=current_user.email, purpose=EMAIL_PURPOSE_VERIFICATION
    )
    session.commit()
    send_verification_email(
        recipient_email=current_user.email,
        full_name=current_user.full_name,
    )
    return VerificationResponse(detail="We sent a fresh verification email.")


@router.post("/verify-email", response_model=VerificationResponse)
@limiter.limit("10/minute")
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> VerificationResponse:
    normalized_email = payload.email.lower()
    if not verify_email_verification_code(normalized_email, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That verification link is invalid.",
        )
    user = session.exec(
        select(User).where(User.email == normalized_email)
    ).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account exists for that verification link.",
        )
    if user.email_validated:
        return VerificationResponse(detail="Your email is already verified.")
    user.email_validated = True
    session.add(user)
    session.commit()
    return VerificationResponse(detail="Your email has been verified.")


@router.post("/magic-login/request", response_model=VerificationResponse)
@limiter.limit("3/hour")
def request_magic_login(
    payload: MagicLoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> VerificationResponse:
    normalized_email = payload.email.lower()
    user = session.exec(
        select(User).where(User.email == normalized_email)
    ).one_or_none()
    if not user:
        return VerificationResponse(detail=MAGIC_LOGIN_REQUEST_MESSAGE)
    require_auth_email_cooldown(
        session,
        email=user.email,
        purpose=EMAIL_PURPOSE_MAGIC_LOGIN,
        cooldown_seconds=settings.MAGIC_LOGIN_COOLDOWN_SECONDS,
    )
    expires_at = build_magic_login_expires_at()
    magic_url = build_magic_login_url(user.email, expires_at, user.password_hash)
    record_auth_email_send(
        session, email=user.email, purpose=EMAIL_PURPOSE_MAGIC_LOGIN
    )
    session.commit()
    send_magic_login_email(
        recipient_email=user.email,
        full_name=user.full_name,
        magic_url=magic_url,
    )
    return VerificationResponse(detail=MAGIC_LOGIN_REQUEST_MESSAGE)


@router.post("/magic-login/consume", response_model=UserResponse)
@limiter.limit("10/minute")
def consume_magic_login(
    payload: MagicLoginConsumeRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> UserResponse:
    normalized_email = payload.email.lower()
    user = session.exec(
        select(User).where(User.email == normalized_email)
    ).one_or_none()
    if not user or not verify_magic_login_code(
        normalized_email, payload.expires, user.password_hash, payload.code
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That sign-in link is invalid or expired.",
        )
    store_user_session(request, user)
    return UserResponse.model_validate(user)


@router.post("/password-reset/request", response_model=VerificationResponse)
@limiter.limit("3/hour")
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> VerificationResponse:
    normalized_email = payload.email.lower()
    user = session.exec(
        select(User).where(User.email == normalized_email)
    ).one_or_none()
    if not user:
        return VerificationResponse(detail=PASSWORD_RESET_REQUEST_MESSAGE)
    retry_after = get_auth_email_retry_after_seconds(
        session,
        email=user.email,
        purpose=EMAIL_PURPOSE_PASSWORD_RESET,
        cooldown_seconds=settings.PASSWORD_RESET_COOLDOWN_SECONDS,
    )
    if retry_after is not None:
        return VerificationResponse(detail=PASSWORD_RESET_REQUEST_MESSAGE)
    expires_at = build_password_reset_expires_at()
    reset_url = build_password_reset_url(user.email, expires_at, user.password_hash)
    record_auth_email_send(
        session, email=user.email, purpose=EMAIL_PURPOSE_PASSWORD_RESET
    )
    session.commit()
    send_password_reset_email(
        recipient_email=user.email,
        full_name=user.full_name,
        reset_url=reset_url,
    )
    return VerificationResponse(detail=PASSWORD_RESET_REQUEST_MESSAGE)


@router.post("/password-reset/consume", response_model=UserResponse)
@limiter.limit("10/minute")
def consume_password_reset(
    payload: PasswordResetConsumeRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> UserResponse:
    normalized_email = payload.email.lower()
    user = session.exec(
        select(User).where(User.email == normalized_email)
    ).one_or_none()
    if not user or not verify_password_reset_code(
        normalized_email, payload.expires, user.password_hash, payload.code
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That password reset link is invalid or expired.",
        )
    user.password_hash = hash_password(payload.password)
    user.session_version += 1
    session.add(user)
    session.commit()
    session.refresh(user)
    store_user_session(request, user)
    return UserResponse.model_validate(user)


@router.get("/google/start")
def google_start(request: Request, mode: str = "login") -> RedirectResponse:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=GOOGLE_SIGN_IN_FAILED_DETAIL,
        )
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_mode"] = mode if mode == "register" else "login"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    )


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    expected_state = request.session.pop("google_oauth_state", None)
    mode = request.session.pop("google_oauth_mode", "login")
    if error:
        return _auth_redirect(error="Google sign-in was cancelled.", mode=mode)
    if not code or not state or not expected_state or state != expected_state:
        return _auth_redirect(error="Google sign-in could not be verified.", mode=mode)
    try:
        token_payload = _exchange_google_code(code)
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return _auth_redirect(
                error="Google sign-in did not return an access token.", mode=mode
            )
        profile = _fetch_google_profile(access_token)
    except Exception:
        logger.exception("Google OAuth callback failed.")
        return _auth_redirect(error="Google sign-in failed. Please try again.", mode=mode)
    if not profile.email_verified:
        return _auth_redirect(error="Google email verification is required.", mode=mode)
    try:
        user = _upsert_google_user(session, profile)
    except ValueError:
        return _auth_redirect(error="That Google account cannot be linked.", mode=mode)
    store_user_session(request, user)
    return RedirectResponse(f"{settings.BASE_URL.rstrip('/')}/app")


@router.post("/google/one-tap", response_model=UserResponse)
def google_one_tap(
    payload: GoogleOneTapRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> UserResponse:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=GOOGLE_SIGN_IN_FAILED_DETAIL,
        )
    try:
        profile = _verify_google_credential(payload.credential)
    except GoogleCredentialConfigurationError as error:
        logger.warning("Google One Tap is not configured correctly: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=GOOGLE_SIGN_IN_FAILED_DETAIL,
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error) or "Google sign-in could not be verified.",
        ) from error
    if not profile.email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email verification is required.",
        )
    try:
        user = _upsert_google_user(session, profile)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "That Google account cannot be linked.",
        ) from error
    store_user_session(request, user)
    return UserResponse.model_validate(user)


def _upsert_google_user(session: Session, profile: GoogleProfile) -> User:
    email = str(profile.email).lower()
    subject_user = session.exec(
        select(User).where(User.google_subject == profile.sub)
    ).one_or_none()
    email_user = session.exec(select(User).where(User.email == email)).one_or_none()
    if subject_user and subject_user.email != email:
        raise ValueError("Google account is already linked to another user.")
    if email_user and email_user.google_subject not in {None, profile.sub}:
        raise ValueError("User is already linked to another Google account.")
    user = email_user or subject_user
    if user is None:
        user = User(
            email=email,
            email_validated=True,
            full_name=(profile.name or email.split("@", 1)[0]).strip(),
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
    elif profile.name and not user.full_name.strip():
        user.full_name = profile.name.strip()
    user.email_validated = True
    user.google_subject = profile.sub
    if profile.picture:
        user.profile_picture_url = str(profile.picture)[:2048]
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _google_redirect_uri() -> str:
    return f"{settings.API_URL.rstrip('/')}/auth/google/callback"


def _auth_redirect(
    *, error: str | None = None, mode: str | None = None
) -> RedirectResponse:
    params: dict[str, str] = {}
    if error:
        params["auth_error"] = error
    if mode in {"login", "register"}:
        params["mode"] = mode
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{settings.BASE_URL.rstrip('/')}/{query}")


def _exchange_google_code(code: str) -> dict[str, Any]:
    payload = urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": _google_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = UrlRequest(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return _request_json(request)


def _fetch_google_profile(access_token: str) -> GoogleProfile:
    request = UrlRequest(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return GoogleProfile.model_validate(_request_json(request))


def _verify_google_credential(credential: str) -> GoogleProfile:
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as error:
        raise GoogleCredentialConfigurationError(
            "Install google-auth[requests] to verify Google One Tap credentials."
        ) from error
    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception as error:
        raise ValueError(
            "Google sign-in could not be verified. Check GOOGLE_CLIENT_ID."
        ) from error
    return GoogleProfile.model_validate(claims)


def _request_json(request: UrlRequest) -> dict[str, Any]:
    if request.type != "https":
        raise ValueError("Only HTTPS Google OAuth requests are allowed.")
    with urlopen(request, timeout=20) as response:  # nosec B310
        payload = response.read()
    return json.loads(payload.decode("utf-8"))
