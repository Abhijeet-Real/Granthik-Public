from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user, get_current_active_superuser
from app.crud import role as role_crud
from app.db.models import User, Role, Permission
from app.schemas.role import (
    Role as RoleSchema,
    RoleCreate,
    RoleUpdate,
    Permission as PermissionSchema,
    PermissionCreate,
    PermissionUpdate,
    RoleWithUsers
)

router = APIRouter()

# Role endpoints
@router.get("/", response_model=List[RoleSchema])
def read_roles(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    is_default: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Retrieve roles.
    """
    # Only superusers can list all roles
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    filter_params = {}
    if name:
        filter_params["name"] = name
    if is_default is not None:
        filter_params["is_default"] = is_default
    
    roles = role_crud.get_roles(db, skip=skip, limit=limit, filter_params=filter_params)
    return roles

@router.get("/with-users", response_model=List[RoleWithUsers])
def read_roles_with_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Retrieve roles with user counts.
    """
    roles = role_crud.get_roles(db)
    
    # Add user count to each role
    result = []
    for role in roles:
        role_data = RoleWithUsers.from_orm(role)
        role_data.user_count = len(role.users)
        result.append(role_data)
    
    return result

@router.post("/", response_model=RoleSchema)
def create_role(
    *,
    db: Session = Depends(get_db),
    role_in: RoleCreate,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Create new role.
    """
    role = role_crud.get_role_by_name(db, name=role_in.name)
    if role:
        raise HTTPException(
            status_code=400,
            detail="Role with this name already exists"
        )
    
    role = role_crud.create_role(db, role_in=role_in)
    return role

@router.get("/{role_id}", response_model=RoleSchema)
def read_role(
    *,
    db: Session = Depends(get_db),
    role_id: int,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get role by ID.
    """
    role = role_crud.get_role(db, role_id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Only superusers can view roles
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return role

@router.put("/{role_id}", response_model=RoleSchema)
def update_role(
    *,
    db: Session = Depends(get_db),
    role_id: int,
    role_in: RoleUpdate,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Update a role.
    """
    role = role_crud.get_role(db, role_id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    role = role_crud.update_role(db, role_id=role_id, role_in=role_in)
    return role

@router.delete("/{role_id}", response_model=RoleSchema)
def delete_role(
    *,
    db: Session = Depends(get_db),
    role_id: int,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Delete a role.
    """
    role = role_crud.get_role(db, role_id=role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Prevent deletion of roles with users
    if role.users:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete role with assigned users"
        )
    
    role_crud.delete_role(db, role_id=role_id)
    return role

# Permission endpoints
@router.get("/permissions/", response_model=List[PermissionSchema])
def read_permissions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Retrieve permissions.
    """
    filter_params = {}
    if name:
        filter_params["name"] = name
    if resource:
        filter_params["resource"] = resource
    if action:
        filter_params["action"] = action
    
    permissions = role_crud.get_permissions(db, skip=skip, limit=limit, filter_params=filter_params)
    return permissions

@router.post("/permissions/", response_model=PermissionSchema)
def create_permission(
    *,
    db: Session = Depends(get_db),
    permission_in: PermissionCreate,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Create new permission.
    """
    permission = role_crud.get_permission_by_name(db, name=permission_in.name)
    if permission:
        raise HTTPException(
            status_code=400,
            detail="Permission with this name already exists"
        )
    
    permission = role_crud.create_permission(db, permission_in=permission_in)
    return permission

@router.get("/permissions/{permission_id}", response_model=PermissionSchema)
def read_permission(
    *,
    db: Session = Depends(get_db),
    permission_id: int,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Get permission by ID.
    """
    permission = role_crud.get_permission(db, permission_id=permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    return permission

@router.put("/permissions/{permission_id}", response_model=PermissionSchema)
def update_permission(
    *,
    db: Session = Depends(get_db),
    permission_id: int,
    permission_in: PermissionUpdate,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Update a permission.
    """
    permission = role_crud.get_permission(db, permission_id=permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    permission = role_crud.update_permission(db, permission_id=permission_id, permission_in=permission_in)
    return permission

@router.delete("/permissions/{permission_id}", response_model=PermissionSchema)
def delete_permission(
    *,
    db: Session = Depends(get_db),
    permission_id: int,
    current_user: User = Depends(get_current_active_superuser)
) -> Any:
    """
    Delete a permission.
    """
    permission = role_crud.get_permission(db, permission_id=permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # Prevent deletion of permissions assigned to roles
    if permission.roles:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete permission assigned to roles"
        )
    
    role_crud.delete_permission(db, permission_id=permission_id)
    return permission