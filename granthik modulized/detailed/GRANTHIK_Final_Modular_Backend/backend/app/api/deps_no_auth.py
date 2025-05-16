from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.crud.user import get_user, get_user_by_email
from app.db.models import User

# This is a simplified version that doesn't require authentication tokens
# It will use a default admin user for all operations

def get_current_user(
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current user without requiring authentication.
    This will always return the admin user for simplicity.
    """
    # Get the admin user
    user = get_user_by_email(db, email="admin@example.com")
    if not user:
        # If admin doesn't exist, try to find any active user
        users = db.query(User).filter(User.is_active == True).all()
        if users:
            user = users[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No active users found in the system",
            )
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current active user.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current active superuser.
    This will always succeed since we're using the admin user.
    """
    # We're using the admin user, so this should always be a superuser
    if not current_user.is_superuser:
        # If for some reason the user is not a superuser, make them one
        current_user.is_superuser = True
    return current_user