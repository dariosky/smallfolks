import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import Session, desc, select

import settings
from models.auth import AuthEmailSend

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
EMAIL_PURPOSE_MAGIC_LOGIN = "magic_login"
EMAIL_PURPOSE_PASSWORD_RESET = "password_reset"  # nosec B105:hardcoded_password_string
EMAIL_PURPOSE_VERIFICATION = "email_verification"
EMAIL_VERIFICATION_TOKEN_SALT = "email-verification"  # nosec B105


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, expected_digest = stored_hash.split("$", maxsplit=1)
    candidate_digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    ).hex()
    return hmac.compare_digest(candidate_digest, expected_digest)


def _email_verification_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=settings.SESSION_SECRET_KEY,
        salt=EMAIL_VERIFICATION_TOKEN_SALT,
    )


def build_email_verification_code(email: str) -> str:
    return _email_verification_serializer().dumps(
        {"email": email.strip().lower(), "nonce": secrets.token_urlsafe(16)}
    )


def verify_email_verification_code(email: str, code: str) -> bool:
    try:
        payload = _email_verification_serializer().loads(
            code.strip(),
            max_age=settings.EMAIL_VERIFICATION_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        return False
    if not isinstance(payload, dict):
        return False
    token_email = payload.get("email")
    if not isinstance(token_email, str):
        return False
    return hmac.compare_digest(token_email, email.strip().lower())


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_auth_email_retry_after_seconds(
    session: Session, *, email: str, purpose: str, cooldown_seconds: int
) -> int | None:
    if cooldown_seconds <= 0:
        return None

    latest_send = session.exec(
        select(AuthEmailSend)
        .where(AuthEmailSend.email == email.strip().lower())
        .where(AuthEmailSend.purpose == purpose)
        .order_by(desc(AuthEmailSend.sent_at))
    ).first()
    if latest_send is None:
        return None

    elapsed = datetime.now(UTC) - normalize_utc(latest_send.sent_at)
    cooldown = timedelta(seconds=cooldown_seconds)
    if elapsed >= cooldown:
        return None
    return max(1, int((cooldown - elapsed).total_seconds()))


def record_auth_email_send(session: Session, *, email: str, purpose: str) -> None:
    session.add(AuthEmailSend(email=email.strip().lower(), purpose=purpose))


def build_password_reset_expires_at() -> int:
    return int(time.time()) + settings.PASSWORD_RESET_MAX_AGE_SECONDS


def build_magic_login_expires_at() -> int:
    return int(time.time()) + settings.MAGIC_LOGIN_MAX_AGE_SECONDS


def build_magic_login_code(email: str, expires_at: int, password_hash: str) -> str:
    message = f"magic-login:{email.strip().lower()}:{expires_at}:{password_hash}"
    return hmac.new(
        settings.SESSION_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_magic_login_url(email: str, expires_at: int, password_hash: str) -> str:
    query = urlencode(
        {
            "email": email,
            "expires": str(expires_at),
            "code": build_magic_login_code(email, expires_at, password_hash),
        }
    )
    return f"{settings.BASE_URL.rstrip('/')}/magic-login?{query}"


def verify_magic_login_code(
    email: str, expires_at: int, password_hash: str, code: str
) -> bool:
    if expires_at < int(time.time()):
        return False
    expected_code = build_magic_login_code(email, expires_at, password_hash)
    return hmac.compare_digest(expected_code, code.strip())


def build_password_reset_code(email: str, expires_at: int, password_hash: str) -> str:
    message = f"password-reset:{email.strip().lower()}:{expires_at}:{password_hash}"
    return hmac.new(
        settings.SESSION_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_password_reset_url(email: str, expires_at: int, password_hash: str) -> str:
    query = urlencode(
        {
            "email": email,
            "expires": str(expires_at),
            "code": build_password_reset_code(email, expires_at, password_hash),
        }
    )
    return f"{settings.BASE_URL.rstrip('/')}/reset-password?{query}"


def verify_password_reset_code(
    email: str, expires_at: int, password_hash: str, code: str
) -> bool:
    if expires_at < int(time.time()):
        return False
    expected_code = build_password_reset_code(email, expires_at, password_hash)
    return hmac.compare_digest(expected_code, code.strip())
