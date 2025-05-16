from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from . import schema, crud
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/users", response_model=schema.UserOut)
def create_user(user: schema.UserCreate, db: Session = Depends(get_db)):
    return crud.create_user(db, user)

@router.get("/users", response_model=list[schema.UserOut])
def get_users(db: Session = Depends(get_db)):
    return crud.list_users(db)

@router.post("/groups", response_model=schema.GroupOut)
def create_group(group: schema.GroupCreate, db: Session = Depends(get_db)):
    return crud.create_group(db, group)

@router.get("/groups", response_model=list[schema.GroupOut])
def get_groups(db: Session = Depends(get_db)):
    return crud.list_groups(db)