from typing import Any, List, Dict
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate, UserWithPermissions
from app.schemas.role import Role as RoleSchema, Permission as PermissionSchema
from app.crud import user as user_crud
from app.crud import role as role_crud
from app.api.deps import get_current_user, get_db, get_current_active_superuser, get_current_active_user
from app.services.email import send_email
from app.schemas.email import EmailMessage

router = APIRouter()

@router.get("/users/me", response_model=UserSchema)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user information
    """
    return current_user

@router.put("/users/me", response_model=UserSchema)
def update_current_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update current user
    """
    user = user_crud.update_user(db, db_obj=current_user, obj_in=user_in)
    return user

@router.get("/users", response_model=List[UserSchema])
def get_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Get all users (superuser only)
    """
    users = user_crud.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/users/pending", response_model=List[UserSchema])
def get_pending_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Get all users pending approval (superuser only)
    """
    users = user_crud.get_pending_users(db)
    return users

@router.post("/users", response_model=UserSchema)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Create new user (superuser only)
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    user = user_crud.get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    
    # Always generate a random password for new users
    # Generate a secure random password (avoiding special characters that might cause issues)
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(12))
    original_password = password  # Store for email
    user_in.password = password
    temp_password = True
    
    # When admin creates a user, automatically approve them
    user_in.is_approved = True
    user_in.approval_status = "approved"
    user_in.is_active = True
    
    logger.info(f"Creating new user: {user_in.email} with temporary password (auto-approved)")
    
    # Create the user
    user = user_crud.create_user(db, obj_in=user_in)
    
    # Send welcome email with password
    try:
        logger.info(f"Sending welcome email to {user_in.email}")
        
        email_body = f"""
        <html>
        <body>
        <h2>Welcome to GRANTHIK!</h2>
        <p>Your account has been created successfully.</p>
        <p><strong>Username:</strong> {user_in.username}</p>
        <p><strong>Email:</strong> {user_in.email}</p>
        <p><strong>Temporary Password:</strong> {original_password}</p>
        <p>Please login and change your password as soon as possible.</p>
        <p>Thank you for joining GRANTHIK!</p>
        </body>
        </html>
        """
        
        email_message = EmailMessage(
            to=user_in.email,
            subject="Welcome to GRANTHIK - Account Created",
            body=email_body
        )
        
        result = send_email(email_message)
        if result["success"]:
            logger.info(f"Welcome email sent successfully to {user_in.email}")
        else:
            logger.error(f"Failed to send welcome email: {result['message']}")
            
    except Exception as e:
        # Log the error but don't prevent user creation
        logger.error(f"Exception sending welcome email: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    return user

@router.get("/users/{user_id}", response_model=UserSchema)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Get a specific user by id (superuser only)
    """
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    return user

@router.put("/users/{user_id}", response_model=UserSchema)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Update a user (superuser only)
    """
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    user = user_crud.update_user(db, db_obj=user, obj_in=user_in)
    return user

@router.delete("/users/{user_id}", response_model=UserSchema)
def delete_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Delete a user (superuser only)
    """
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    # Protected emails that cannot be deleted
    protected_emails = ["admin@granthik.com", "321148@fsm.ac.in"]
    
    if user.email in protected_emails:
        raise HTTPException(
            status_code=403,
            detail="This user account is protected and cannot be deleted",
        )
    
    user = user_crud.delete_user(db, id=user_id)
    return user

@router.post("/users/{user_id}/approve", response_model=UserSchema)
def approve_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Approve a user registration (superuser only)
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    # Update user status
    user_update = UserUpdate(
        is_active=True,
        is_approved=True,
        approval_status="approved"
    )
    
    # Force commit to ensure database is updated
    # Update directly in the database to ensure all fields are properly set
    user.is_active = True
    user.is_approved = True
    user.approval_status = "approved"
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Also update using the CRUD function for consistency
    updated_user = user_crud.update_user(db, db_obj=user, obj_in=user_update)
    db.commit()
    db.refresh(updated_user)
    
    # Send approval notification to user
    try:
        email_body = f"""
        <html>
        <body>
        <h2>Account Approved</h2>
        <p>Your GRANTHIK account has been approved!</p>
        <p>You can now log in with your credentials.</p>
        <p><strong>Username:</strong> {user.username}</p>
        <p><strong>Email:</strong> {user.email}</p>
        </body>
        </html>
        """
        
        email_message = EmailMessage(
            to=user.email,
            subject="GRANTHIK - Account Approved",
            body=email_body
        )
        
        result = send_email(email_message)
        if result["success"]:
            logger.info(f"Approval notification sent to {user.email}")
        else:
            logger.error(f"Failed to send approval email: {result['message']}")
    except Exception as e:
        # Log the error but don't prevent user approval
        logger.error(f"Error sending approval notification: {str(e)}")
    
    return updated_user

@router.post("/users/{user_id}/reject", response_model=UserSchema)
def reject_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Reject a user registration (superuser only)
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    # Update user status
    user_update = UserUpdate(
        is_active=False,
        is_approved=False,
        approval_status="rejected"
    )
    
    updated_user = user_crud.update_user(db, db_obj=user, obj_in=user_update)
    
    # Send rejection notification to user
    try:
        email_body = f"""
        <html>
        <body>
        <h2>Account Registration Rejected</h2>
        <p>We're sorry, but your GRANTHIK account registration has been rejected.</p>
        <p>Please contact the administrator for more information.</p>
        </body>
        </html>
        """
        
        email_message = EmailMessage(
            to=user.email,
            subject="GRANTHIK - Account Registration Rejected",
            body=email_body
        )
        
        result = send_email(email_message)
        if result["success"]:
            logger.info(f"Rejection notification sent to {user.email}")
        else:
            logger.error(f"Failed to send rejection email: {result['message']}")
    except Exception as e:
        # Log the error but don't prevent user rejection
        logger.error(f"Error sending rejection notification: {str(e)}")
    
    return updated_user

@router.post("/users/{user_id}/reset-password", response_model=Dict[str, Any])
def reset_user_password(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Reset a user's password (superuser only)
    """
    import logging
    import secrets
    import string
    
    logger = logging.getLogger("uvicorn")
    
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    # Generate a secure random password
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(12))
    
    # Update user password
    user_update = UserUpdate(
        password=password,
        password_reset_required=True
    )
    
    updated_user = user_crud.update_user(db, db_obj=user, obj_in=user_update)
    
    # Send password reset notification to user
    try:
        email_body = f"""
        <html>
        <body>
        <h2>Password Reset</h2>
        <p>Your GRANTHIK account password has been reset by an administrator.</p>
        <p><strong>Username:</strong> {user.username}</p>
        <p><strong>Email:</strong> {user.email}</p>
        <p><strong>Temporary Password:</strong> {password}</p>
        <p>Please login and change your password as soon as possible.</p>
        </body>
        </html>
        """
        
        email_message = EmailMessage(
            to=user.email,
            subject="GRANTHIK - Password Reset",
            body=email_body
        )
        
        result = send_email(email_message)
        if result["success"]:
            logger.info(f"Password reset notification sent to {user.email}")
        else:
            logger.error(f"Failed to send password reset email: {result['message']}")
            
        return {
            "success": True,
            "message": "Password reset successfully",
            "email_sent": result["success"]
        }
    except Exception as e:
        # Log the error but don't prevent password reset
        logger.error(f"Error sending password reset notification: {str(e)}")
        
        return {
            "success": True,
            "message": "Password reset successfully, but failed to send email notification",
            "email_sent": False
        }

@router.get("/users/{user_id}/permissions", response_model=UserWithPermissions)
def get_user_permissions(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a user's permissions
    """
    # Check if the user is requesting their own permissions or is a superuser
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions to access this user's permissions",
        )
    
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    # Get user permissions
    permissions = user_crud.get_user_permission_strings(db, user_id=user_id)
    
    # Create response
    user_with_permissions = UserWithPermissions.from_orm(user)
    user_with_permissions.permissions = permissions
    
    return user_with_permissions

@router.get("/users/{user_id}/roles", response_model=List[RoleSchema])
def get_user_roles(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a user's roles
    """
    # Check if the user is requesting their own roles or is a superuser
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions to access this user's roles",
        )
    
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    return user.roles

@router.post("/users/{user_id}/roles/{role_id}", response_model=UserSchema)
def add_role_to_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Add a role to a user (superuser only)
    """
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    role = role_crud.get_role(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found",
        )
    
    user = user_crud.add_user_to_role(db, user_id=user_id, role_id=role_id)
    return user

@router.delete("/users/{user_id}/roles/{role_id}", response_model=UserSchema)
def remove_role_from_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Remove a role from a user (superuser only)
    """
    user = user_crud.get_user(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    role = role_crud.get_role(db, role_id=role_id)
    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found",
        )
    
    # Check if this is the user's only role
    if len(user.roles) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the user's only role",
        )
    
    user = user_crud.remove_user_from_role(db, user_id=user_id, role_id=role_id)
    return user