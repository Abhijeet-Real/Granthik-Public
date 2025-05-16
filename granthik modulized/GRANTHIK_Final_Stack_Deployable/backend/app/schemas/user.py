from typing import Optional, List
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime
from .role import Role

# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    is_active: Optional[bool] = False  # Changed default to False - requires approval
    is_superuser: bool = False
    is_approved: Optional[bool] = False
    approval_status: Optional[str] = "pending"  # pending, approved, rejected
    password_reset_required: Optional[bool] = True

# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    username: str
    password: str
    role_ids: Optional[List[int]] = []
    group_ids: Optional[List[int]] = []
    
    # Add validation for password
    @validator('password')
    def password_must_be_strong(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v
        
    # Add validation for username
    @validator('username')
    def username_must_be_valid(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if not v.isalnum() and not '_' in v and not '-' in v:
            raise ValueError('Username must contain only alphanumeric characters, underscores, or hyphens')
        return v

# Properties to receive via API on update
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_ids: Optional[List[int]] = None
    group_ids: Optional[List[int]] = None

# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Additional properties to return via API
class User(UserInDBBase):
    roles: Optional[List[Role]] = []

# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str

# User with permissions
class UserWithPermissions(User):
    permissions: List[str] = []