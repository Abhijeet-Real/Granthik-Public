from typing import List, Optional, Dict, Any, Union

from sqlalchemy.orm import Session

from app.db.models import Tag
from app.schemas.tag import TagCreate, TagUpdate


def get_tag(db: Session, tag_id: int) -> Optional[Tag]:
    """Get a tag by ID"""
    return db.query(Tag).filter(Tag.id == tag_id).first()


def get_tag_by_name(db: Session, name: str) -> Optional[Tag]:
    """Get a tag by name"""
    return db.query(Tag).filter(Tag.name == name).first()


def get_tags(
    db: Session, skip: int = 0, limit: int = 100
) -> List[Tag]:
    """Get all tags"""
    return db.query(Tag).offset(skip).limit(limit).all()


def create_tag(db: Session, tag_in: TagCreate) -> Tag:
    """Create a new tag"""
    db_tag = Tag(
        name=tag_in.name,
        color=tag_in.color,
    )
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag


def update_tag(
    db: Session, db_obj: Tag, obj_in: Union[TagUpdate, Dict[str, Any]]
) -> Tag:
    """Update a tag"""
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    for field in update_data:
        if field in update_data:
            setattr(db_obj, field, update_data[field])
    
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_tag(db: Session, tag_id: int) -> Tag:
    """Delete a tag"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if tag:
        db.delete(tag)
        db.commit()
    return tag