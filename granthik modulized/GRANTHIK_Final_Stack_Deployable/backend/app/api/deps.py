from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.core.security import oauth2_scheme
from app.schemas.token import TokenPayload
from app.crud.user import get_user
from app.db.models import User

def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = get_user(db, id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user