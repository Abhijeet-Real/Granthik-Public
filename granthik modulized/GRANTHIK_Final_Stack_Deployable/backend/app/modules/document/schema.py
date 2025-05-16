from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DocumentBase(BaseModel):
    filename: str
    filetype: Optional[str] = None

class DocumentCreate(DocumentBase):
    filepath: str
    uploaded_by: str

class DocumentOut(DocumentBase):
    id: int
    uploaded_by: str
    uploaded_at: datetime
    status: str

    class Config:
        orm_mode = True