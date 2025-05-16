from typing import Any, Dict, Optional, Union, List

from sqlalchemy.orm import Session

from app.db.models import Group, User
from app.schemas.group import GroupCreate, GroupUpdate

def get_group(db: Session, id: int) -> Optional[Group]:
    return db.query(Group).filter(Group.id == id).first()

def get_group_by_name(db: Session, name: str) -> Optional[Group]:
    return db.query(Group).filter(Group.name == name).first()

def get_groups(db: Session, skip: int = 0, limit: int = 100) -> List[Group]:
    return db.query(Group).offset(skip).limit(limit).all()

def get_user_groups(db: Session, user_id: int) -> List[Group]:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        return user.groups
    return []

def create_group(db: Session, obj_in: GroupCreate) -> Group:
    db_obj = Group(
        name=obj_in.name,
        description=obj_in.description,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_group(
    db: Session, *, db_obj: Group, obj_in: Union[GroupUpdate, Dict[str, Any]]
) -> Group:
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

def delete_group(db: Session, *, id: int) -> Group:
    obj = db.query(Group).get(id)
    db.delete(obj)
    db.commit()
    return obj

def add_user_to_group(db: Session, *, group_id: int, user_id: int) -> Optional[Group]:
    group = get_group(db, id=group_id)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not group or not user:
        return None
    
    if user not in group.users:
        group.users.append(user)
        db.commit()
        db.refresh(group)
    
    return group

def remove_user_from_group(db: Session, *, group_id: int, user_id: int) -> Optional[Group]:
    group = get_group(db, id=group_id)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not group or not user:
        return None
    
    if user in group.users:
        group.users.remove(user)
        db.commit()
        db.refresh(group)
    
    return group