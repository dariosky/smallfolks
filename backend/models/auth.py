from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=255)
    email_validated: bool = Field(default=False, nullable=False)
    is_admin: bool = Field(default=False, nullable=False)
    full_name: str = Field(max_length=255)
    password_hash: str = Field(max_length=255)
    profile_picture_url: str | None = Field(default=None, max_length=2048)
    google_subject: str | None = Field(
        default=None, index=True, unique=True, max_length=255
    )
    session_version: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!r}, email={self.email!r}, "
            f"email_validated={self.email_validated!r}, "
            f"is_admin={self.is_admin!r}, full_name={self.full_name!r}, "
            f"created_at={self.created_at!r})"
        )


class AuthEmailSend(SQLModel, table=True):
    __tablename__ = "auth_email_sends"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, max_length=255)
    purpose: str = Field(index=True, max_length=64)
    sent_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
