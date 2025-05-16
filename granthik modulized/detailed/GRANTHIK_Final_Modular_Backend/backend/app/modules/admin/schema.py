from pydantic import BaseModel
from typing import Optional

class GroupBase(BaseModel):
    name: str

class GroupCreate(GroupBase):
    pass

class GroupOut(GroupBase):
    id: int
    class Config:
        orm_mode = True

class UserBase(BaseModel):
    name: str
    email: str
    role: Optional[str] = "user"
    group_id: Optional[int]

class UserCreate(UserBase):
    pass

class UserOut(UserBase):
    id: int
    class Config:
        orm_mode = True