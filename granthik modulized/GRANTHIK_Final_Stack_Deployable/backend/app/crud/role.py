from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.models import Role, Permission, user_role, role_permission
from app.schemas.role import RoleCreate, RoleUpdate, PermissionCreate, PermissionUpdate

# Role CRUD operations
def get_role(db: Session, role_id: int) -> Optional[Role]:
    return db.query(Role).filter(Role.id == role_id).first()

def get_role_by_name(db: Session, name: str) -> Optional[Role]:
    return db.query(Role).filter(Role.name == name).first()

def get_roles(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    filter_params: Optional[Dict[str, Any]] = None
) -> List[Role]:
    query = db.query(Role)
    
    # Apply filters if provided
    if filter_params:
        if filter_params.get("name"):
            query = query.filter(Role.name.ilike(f"%{filter_params['name']}%"))
        if filter_params.get("is_default") is not None:
            query = query.filter(Role.is_default == filter_params["is_default"])
    
    return query.offset(skip).limit(limit).all()

def create_role(db: Session, role_in: RoleCreate) -> Role:
    # Create role
    db_role = Role(
        name=role_in.name,
        description=role_in.description,
        is_default=role_in.is_default
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    # Add permissions if provided
    if role_in.permission_ids:
        for permission_id in role_in.permission_ids:
            db.execute(
                role_permission.insert().values(
                    role_id=db_role.id,
                    permission_id=permission_id
                )
            )
        db.commit()
        db.refresh(db_role)
    
    return db_role

def update_role(db: Session, role_id: int, role_in: RoleUpdate) -> Optional[Role]:
    db_role = get_role(db, role_id)
    if not db_role:
        return None
    
    # Update role attributes
    update_data = role_in.dict(exclude_unset=True)
    permission_ids = update_data.pop("permission_ids", None)
    
    for key, value in update_data.items():
        setattr(db_role, key, value)
    
    # Update permissions if provided
    if permission_ids is not None:
        # Remove existing permissions
        db.execute(
            role_permission.delete().where(role_permission.c.role_id == role_id)
        )
        
        # Add new permissions
        for permission_id in permission_ids:
            db.execute(
                role_permission.insert().values(
                    role_id=role_id,
                    permission_id=permission_id
                )
            )
    
    db.commit()
    db.refresh(db_role)
    return db_role

def delete_role(db: Session, role_id: int) -> bool:
    db_role = get_role(db, role_id)
    if not db_role:
        return False
    
    # Remove role-permission associations
    db.execute(
        role_permission.delete().where(role_permission.c.role_id == role_id)
    )
    
    # Remove user-role associations
    db.execute(
        user_role.delete().where(user_role.c.role_id == role_id)
    )
    
    # Delete the role
    db.delete(db_role)
    db.commit()
    return True

# Permission CRUD operations
def get_permission(db: Session, permission_id: int) -> Optional[Permission]:
    return db.query(Permission).filter(Permission.id == permission_id).first()

def get_permission_by_name(db: Session, name: str) -> Optional[Permission]:
    return db.query(Permission).filter(Permission.name == name).first()

def get_permissions(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    filter_params: Optional[Dict[str, Any]] = None
) -> List[Permission]:
    query = db.query(Permission)
    
    # Apply filters if provided
    if filter_params:
        if filter_params.get("name"):
            query = query.filter(Permission.name.ilike(f"%{filter_params['name']}%"))
        if filter_params.get("resource"):
            query = query.filter(Permission.resource == filter_params["resource"])
        if filter_params.get("action"):
            query = query.filter(Permission.action == filter_params["action"])
    
    return query.offset(skip).limit(limit).all()

def create_permission(db: Session, permission_in: PermissionCreate) -> Permission:
    db_permission = Permission(
        name=permission_in.name,
        description=permission_in.description,
        resource=permission_in.resource,
        action=permission_in.action
    )
    db.add(db_permission)
    db.commit()
    db.refresh(db_permission)
    return db_permission

def update_permission(
    db: Session, 
    permission_id: int, 
    permission_in: PermissionUpdate
) -> Optional[Permission]:
    db_permission = get_permission(db, permission_id)
    if not db_permission:
        return None
    
    update_data = permission_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_permission, key, value)
    
    db.commit()
    db.refresh(db_permission)
    return db_permission

def delete_permission(db: Session, permission_id: int) -> bool:
    db_permission = get_permission(db, permission_id)
    if not db_permission:
        return False
    
    # Remove role-permission associations
    db.execute(
        role_permission.delete().where(role_permission.c.permission_id == permission_id)
    )
    
    # Delete the permission
    db.delete(db_permission)
    db.commit()
    return True

# Helper functions
def get_user_permissions(db: Session, user_id: int) -> List[Permission]:
    """Get all permissions for a user based on their roles"""
    return db.query(Permission).join(
        role_permission, Permission.id == role_permission.c.permission_id
    ).join(
        user_role, role_permission.c.role_id == user_role.c.role_id
    ).filter(
        user_role.c.user_id == user_id
    ).all()

def check_user_permission(db: Session, user_id: int, resource: str, action: str) -> bool:
    """Check if a user has a specific permission"""
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