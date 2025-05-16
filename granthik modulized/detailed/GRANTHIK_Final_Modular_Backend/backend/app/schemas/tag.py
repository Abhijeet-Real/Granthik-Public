from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


# Shared properties
class TagBase(BaseModel):
    name: str
    color: Optional[str] = "#3f51b5"


# Properties to receive on tag creation
class TagCreate(TagBase):
    pass


# Properties to receive on tag update
class TagUpdate(TagBase):
    name: Optional[str] = None
    color: Optional[str] = None


# Properties shared by models stored in DB
class TagInDBBase(TagBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# Properties to return to client
class Tag(TagInDBBase):
    pass


# Properties properties stored in DB
class TagInDB(TagInDBBase):
    pass