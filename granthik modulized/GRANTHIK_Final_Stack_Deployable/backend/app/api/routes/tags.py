from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.tag import Tag, TagCreate, TagUpdate
from app.crud import tag as tag_crud
from app.api.deps import get_current_user, get_db

router = APIRouter()

@router.get("/tags", response_model=List[Tag])
def get_tags(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get all tags
    """
    tags = tag_crud.get_tags(db, skip=skip, limit=limit)
    return tags

@router.post("/tags", response_model=Tag)
def create_tag(
    *,
    db: Session = Depends(get_db),
    tag_in: TagCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create a new tag
    """
    # Check if tag with same name already exists
    existing_tag = tag_crud.get_tag_by_name(db, name=tag_in.name)
    if existing_tag:
        raise HTTPException(
            status_code=400,
            detail="Tag with this name already exists",
        )
    
    tag = tag_crud.create_tag(db, tag_in=tag_in)
    return tag

@router.put("/tags/{tag_id}", response_model=Tag)
def update_tag(
    *,
    db: Session = Depends(get_db),
    tag_id: int,
    tag_in: TagUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a tag
    """
    tag = tag_crud.get_tag(db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=404,
            detail="Tag not found",
        )
    
    # Check if new name conflicts with existing tag
    if tag_in.name and tag_in.name != tag.name:
        existing_tag = tag_crud.get_tag_by_name(db, name=tag_in.name)
        if existing_tag:
            raise HTTPException(
                status_code=400,
                detail="Tag with this name already exists",
            )
    
    tag = tag_crud.update_tag(db, db_obj=tag, obj_in=tag_in)
    return tag

@router.delete("/tags/{tag_id}", response_model=Tag)
def delete_tag(
    *,
    db: Session = Depends(get_db),
    tag_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete a tag
    """
    tag = tag_crud.get_tag(db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=404,
            detail="Tag not found",
        )
    
    tag = tag_crud.delete_tag(db, tag_id=tag_id)
    return tag