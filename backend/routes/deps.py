from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from db import get_session
from models.auth import User


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    raw_user_id = request.session.get("user_id")
    if raw_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    user = session.exec(select(User).where(User.id == int(raw_user_id))).one_or_none()
    if user is None:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    stored_version = request.session.get("session_version")
    if stored_version is None or int(stored_version) != user.session_version:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    request.session["user_id"] = user.id
    request.state.user_id = user.id
    return user
