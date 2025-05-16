from sqlalchemy.orm import Session
from . import models, schema

def create_user(db: Session, user: schema.UserCreate):
    db_user = models.User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def list_users(db: Session):
    return db.query(models.User).all()

def create_group(db: Session, group: schema.GroupCreate):
    db_group = models.Group(**group.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def list_groups(db: Session):
    return db.query(models.Group).all()