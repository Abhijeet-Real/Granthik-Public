from typing import Any, Dict, Optional, Union, List

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.security import get_password_hash, verify_password
from app.db.models import User, Group, Role, Permission, user_role, user_group
from app.schemas.user import UserCreate, UserUpdate

def get_user(db: Session, id: int) -> Optional[User]:
    return db.query(User).filter(User.id == id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).order_by(User.username).offset(skip).limit(limit).all()

def get_superusers(db: Session) -> List[User]:
    return db.query(User).filter(User.is_superuser == True).all()

def get_pending_users(db: Session) -> List[User]:
    return db.query(User).filter(User.approval_status == "pending").order_by(User.created_at.desc()).all()

def create_user(db: Session, obj_in: UserCreate) -> User:
    db_obj = User(
        email=obj_in.email,
        username=obj_in.username,
        hashed_password=get_password_hash(obj_in.password),
        is_superuser=obj_in.is_superuser,
        is_active=obj_in.is_active,
        is_approved=obj_in.is_approved if hasattr(obj_in, "is_approved") else False,
        approval_status=obj_in.approval_status if hasattr(obj_in, "approval_status") else "pending",
        password_reset_required=obj_in.password_reset_required if hasattr(obj_in, "password_reset_required") else True
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    # Add user to roles if specified
    if hasattr(obj_in, "role_ids") and obj_in.role_ids:
        for role_id in obj_in.role_ids:
            role = db.query(Role).get(role_id)
            if role:
                db.execute(
                    user_role.insert().values(
                        user_id=db_obj.id,
                        role_id=role_id
                    )
                )
    
    # Add user to groups if specified
    if hasattr(obj_in, "group_ids") and obj_in.group_ids:
        for group_id in obj_in.group_ids:
            group = db.query(Group).get(group_id)
            if group:
                db.execute(
                    user_group.insert().values(
                        user_id=db_obj.id,
                        group_id=group_id
                    )
                )
    
    # If no roles assigned and there's a default role, assign it
    if not hasattr(obj_in, "role_ids") or not obj_in.role_ids:
        default_role = db.query(Role).filter(Role.is_default == True).first()
        if default_role:
            db.execute(
                user_role.insert().values(
                    user_id=db_obj.id,
                    role_id=default_role.id
                )
            )
    
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_user(db: Session, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]) -> User:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    # Handle password update
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
    
    # Handle role updates
    role_ids = update_data.pop("role_ids", None)
    
    # Handle group updates
    group_ids = update_data.pop("group_ids", None)
    
    # Update user attributes
    for field in update_data:
        if field in update_data:
            setattr(db_obj, field, update_data[field])
    
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    # Update roles if specified
    if role_ids is not None:
        # Remove existing roles
        db.execute(
            user_role.delete().where(user_role.c.user_id == db_obj.id)
        )
        
        # Add new roles
        for role_id in role_ids:
            db.execute(
                user_role.insert().values(
                    user_id=db_obj.id,
                    role_id=role_id
                )
            )
    
    # Update groups if specified
    if group_ids is not None:
        # Remove existing groups
        db.execute(
            user_group.delete().where(user_group.c.user_id == db_obj.id)
        )
        
        # Add new groups
        for group_id in group_ids:
            db.execute(
                user_group.insert().values(
                    user_id=db_obj.id,
                    group_id=group_id
                )
            )
    
    db.commit()
    db.refresh(db_obj)
    return db_obj

def delete_user(db: Session, id: int) -> User:
    user = db.query(User).get(id)
    
    # Prevent deletion of admin users with specific emails
    protected_emails = ["admin@granthik.com", "321148@fsm.ac.in"]
    
    if user and user.email not in protected_emails:
        db.delete(user)
        db.commit()
        return user
    elif user and user.email in protected_emails:
        # Return the user but don't delete it
        return user
    return None

def add_user_to_group(db: Session, user_id: int, group_id: int) -> User:
    user = get_user(db, user_id)
    group = db.query(Group).get(group_id)
    
    if user and group:
        user.groups.append(group)
        db.commit()
        db.refresh(user)
    
    return user

def remove_user_from_group(db: Session, user_id: int, group_id: int) -> User:
    user = get_user(db, user_id)
    group = db.query(Group).get(group_id)
    
    if user and group and group in user.groups:
        user.groups.remove(group)
        db.commit()
        db.refresh(user)
    
    return user

def add_user_to_role(db: Session, user_id: int, role_id: int) -> User:
    user = get_user(db, user_id)
    role = db.query(Role).get(role_id)
    
    if user and role:
        # Check if the user already has this role
        existing = db.execute(
            user_role.select().where(
                user_role.c.user_id == user_id,
                user_role.c.role_id == role_id
            )
        ).first()
        
        if not existing:
            db.execute(
                user_role.insert().values(
                    user_id=user_id,
                    role_id=role_id
                )
            )
            db.commit()
            db.refresh(user)
    
    return user

def remove_user_from_role(db: Session, user_id: int, role_id: int) -> User:
    user = get_user(db, user_id)
    role = db.query(Role).get(role_id)
    
    if user and role:
        db.execute(
            user_role.delete().where(
                user_role.c.user_id == user_id,
                user_role.c.role_id == role_id
            )
        )
        db.commit()
        db.refresh(user)
    
    return user

def get_user_permissions(db: Session, user_id: int) -> List[Permission]:
    """Get all permissions for a user based on their roles"""
    return db.query(Permission).join(
        role_permission, Permission.id == role_permission.c.permission_id
    ).join(
        user_role, role_permission.c.role_id == user_role.c.role_id
    ).filter(
        user_role.c.user_id == user_id
    ).all()

def get_user_permission_strings(db: Session, user_id: int) -> List[str]:
    """Get all permission strings for a user in format 'resource:action'"""
    permissions = get_user_permissions(db, user_id)
    return [f"{p.resource}:{p.action}" for p in permissions]

def check_user_permission(db: Session, user_id: int, resource: str, action: str) -> bool:
    """Check if a user has a specific permission"""
    # Superusers have all permissions
    user = get_user(db, user_id)
    if user and user.is_superuser:
        return True
    
    # Check specific permission
    permission_exists = db.query(Permission).join(
        role_permission, Permission.id == role_permission.c.permission_id
    ).join(
        user_role, role_permission.c.role_id == user_role.c.role_id
    ).filter(
        user_role.c.user_id == user_id,
        Permission.resource == resource,
        Permission.action == action
    ).first() is not None
    
    return permission_exists