from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

# Permission schema
class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None
    resource: str
    action: str

class PermissionCreate(PermissionBase):
    pass

class PermissionUpdate(PermissionBase):
    name: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None

class PermissionInDBBase(PermissionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Permission(PermissionInDBBase):
    pass

# Role schema
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: Optional[bool] = False

class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    permission_ids: Optional[List[int]] = None

class RoleInDBBase(RoleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Role(RoleInDBBase):
    permissions: List[Permission] = []

class RoleWithUsers(Role):
    user_count: int = 0