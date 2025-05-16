from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.schemas.token import Token
from app.schemas.user import User, UserCreate
from app.crud.user import get_user_by_email, create_user
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/auth/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    # Try to get user by email first
    user = get_user_by_email(db, email=form_data.username)
    
    # If not found by email, try by username
    if not user:
        from app.crud.user import get_user_by_username
        user = get_user_by_username(db, username=form_data.username)
        
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account is inactive. Please contact an administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_approved and user.approval_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account is pending approval. Please wait for administrator approval.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if user.approval_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your registration has been rejected. Please contact an administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/auth/register", response_model=User)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    Register a new user - public registration with admin approval required
    
    Args:
        user_in: User data including email, username, and password
        
    Returns:
        The created user
        
    Raises:
        HTTPException: If email already exists or validation fails
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    # Check if email already exists
    user = get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    
    # Check if username already exists
    from app.crud.user import get_user_by_username
    user = get_user_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The username is already taken. Please choose another username.",
        )
    
    # Validate password (additional validation beyond schema)
    if not user_in.password or len(user_in.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters long",
        )
    
    # Set user as inactive and pending approval
    user_in.is_active = False
    user_in.is_approved = False
    user_in.approval_status = "pending"
    user_in.password_reset_required = False  # User set their own password
    
    # Create new user
    try:
        user = create_user(db, obj_in=user_in)
        
        # Send notification to admins about new user registration
        try:
            from app.services.email import send_email
            from app.schemas.email import EmailMessage
            from app.crud.user import get_superusers
            
            # Get all superusers
            superusers = get_superusers(db)
            
            if superusers:
                for admin in superusers:
                    # Send email to admin
                    email_body = f"""
                    <html>
                    <body>
                    <h2>New User Registration</h2>
                    <p>A new user has registered and is awaiting approval:</p>
                    <p><strong>Username:</strong> {user.username}</p>
                    <p><strong>Email:</strong> {user.email}</p>
                    <p><strong>Registration Date:</strong> {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Please login to the admin panel to approve or reject this user.</p>
                    </body>
                    </html>
                    """
                    
                    email_message = EmailMessage(
                        to=admin.email,
                        subject="GRANTHIK - New User Registration Awaiting Approval",
                        body=email_body
                    )
                    
                    send_email(email_message)
                    logger.info(f"Admin notification sent to {admin.email}")
            
            # Send confirmation email to user
            user_email_body = f"""
            <html>
            <body>
            <h2>Registration Successful</h2>
            <p>Thank you for registering with GRANTHIK!</p>
            <p>Your account has been created and is pending administrator approval.</p>
            <p>You will receive another email once your account has been approved.</p>
            <p><strong>Username:</strong> {user.username}</p>
            <p><strong>Email:</strong> {user.email}</p>
            </body>
            </html>
            """
            
            user_email_message = EmailMessage(
                to=user.email,
                subject="GRANTHIK - Registration Successful - Awaiting Approval",
                body=user_email_body
            )
            
            send_email(user_email_message)
            logger.info(f"Registration confirmation sent to {user.email}")
            
        except Exception as email_error:
            # Log the error but don't prevent user creation
            logger.error(f"Error sending registration notification: {str(email_error)}")
        
        return user
    except ValueError as e:
        # Handle validation errors from the schema
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        # Handle other errors
        logger.error(f"Error creating user: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error creating user: {str(e)}",
        )

@router.post("/auth/test-token", response_model=User)
def test_token(current_user: User = Depends(get_current_user)) -> Any:
    """
    Test access token
    """
    return current_user