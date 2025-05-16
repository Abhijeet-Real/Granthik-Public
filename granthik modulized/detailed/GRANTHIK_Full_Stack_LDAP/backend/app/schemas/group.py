from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.schemas.user import User

# Shared properties
class GroupBase(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

# Properties to receive via API on creation
class GroupCreate(GroupBase):
    name: str

# Properties to receive via API on update
class GroupUpdate(GroupBase):
    pass

# Properties shared by models stored in DB
class GroupInDBBase(GroupBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Additional properties to return via API
class Group(GroupInDBBase):
    pass

# Group with users
class GroupWithUsers(Group):
    users: List[User] = []