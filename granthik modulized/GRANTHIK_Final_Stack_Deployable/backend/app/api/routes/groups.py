from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.group import Group, GroupCreate, GroupUpdate, GroupWithUsers
from app.crud import group as group_crud
from app.api.deps import get_current_user, get_db, get_current_active_superuser

router = APIRouter()

@router.get("/groups", response_model=List[Group])
def get_groups(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get all groups
    """
    # Superusers can see all groups
    if current_user.is_superuser:
        groups = group_crud.get_groups(db, skip=skip, limit=limit)
    else:
        # Regular users can only see groups they belong to
        groups = group_crud.get_user_groups(db, user_id=current_user.id)
    
    return groups

@router.post("/groups", response_model=Group)
def create_group(
    *,
    db: Session = Depends(get_db),
    group_in: GroupCreate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Create new group (superuser only)
    """
    group = group_crud.get_group_by_name(db, name=group_in.name)
    if group:
        raise HTTPException(
            status_code=400,
            detail="The group with this name already exists",
        )
    group = group_crud.create_group(db, obj_in=group_in)
    return group

@router.get("/groups/{group_id}", response_model=GroupWithUsers)
def get_group(
    *,
    db: Session = Depends(get_db),
    group_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get a specific group
    """
    group = group_crud.get_group(db, id=group_id)
    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group not found",
        )
    
    # Check if user is superuser or belongs to the group
    if not current_user.is_superuser:
        user_group_ids = [g.id for g in current_user.groups]
        if group_id not in user_group_ids:
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions to access this group",
            )
    
    return group

@router.put("/groups/{group_id}", response_model=Group)
def update_group(
    *,
    db: Session = Depends(get_db),
    group_id: int,
    group_in: GroupUpdate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Update a group (superuser only)
    """
    group = group_crud.get_group(db, id=group_id)
    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group not found",
        )
    
    # If name is being updated, check for duplicates
    if group_in.name and group_in.name != group.name:
        existing_group = group_crud.get_group_by_name(db, name=group_in.name)
        if existing_group:
            raise HTTPException(
                status_code=400,
                detail="The group with this name already exists",
            )
    
    group = group_crud.update_group(db, db_obj=group, obj_in=group_in)
    return group

@router.delete("/groups/{group_id}", response_model=Group)
def delete_group(
    *,
    db: Session = Depends(get_db),
    group_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Delete a group (superuser only)
    """
    group = group_crud.get_group(db, id=group_id)
    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group not found",
        )
    group = group_crud.delete_group(db, id=group_id)
    return group

@router.post("/groups/{group_id}/users/{user_id}", response_model=GroupWithUsers)
def add_user_to_group(
    *,
    db: Session = Depends(get_db),
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Add a user to a group (superuser only)
    """
    group = group_crud.add_user_to_group(db, group_id=group_id, user_id=user_id)
    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group or user not found",
        )
    return group

@router.delete("/groups/{group_id}/users/{user_id}", response_model=GroupWithUsers)
def remove_user_from_group(
    *,
    db: Session = Depends(get_db),
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Remove a user from a group (superuser only)
    """
    group = group_crud.remove_user_from_group(db, group_id=group_id, user_id=user_id)
    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group or user not found",
        )
    return group