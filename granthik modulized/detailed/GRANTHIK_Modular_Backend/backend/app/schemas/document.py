from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

from app.schemas.tag import Tag
from app.services.document_processor import ChunkingStrategy

# Shared properties
class DocumentBase(BaseModel):
    filename: Optional[str] = None
    is_public: Optional[bool] = False

# Properties to receive via API on creation
class DocumentCreate(DocumentBase):
    filename: str
    group_ids: List[int] = []
    tag_ids: List[int] = []
    file_path: Optional[str] = None
    file_id: Optional[str] = None
    chunk_count: Optional[int] = 0
    chunk_size: Optional[int] = 1000
    chunk_overlap: Optional[int] = 200
    chunking_strategy: Optional[ChunkingStrategy] = ChunkingStrategy.HYBRID
    processing_status: Optional[str] = "pending"
    processing_progress: Optional[int] = 0
    processing_message: Optional[str] = None
    file_size: Optional[int] = 0
    file_type: Optional[str] = None
    document_type: Optional[str] = None
    brief_summary: Optional[str] = None
    ocr_text: Optional[str] = None

# Properties to receive via API on update
class DocumentUpdate(DocumentBase):
    group_ids: Optional[List[int]] = None
    tag_ids: Optional[List[int]] = None

# Properties shared by models stored in DB
class DocumentInDBBase(DocumentBase):
    id: Optional[int] = None
    file_id: Optional[str] = None
    owner_id: Optional[int] = None
    chunk_count: Optional[int] = 0
    chunk_size: Optional[int] = 1000
    chunk_overlap: Optional[int] = 200
    chunking_strategy: Optional[ChunkingStrategy] = ChunkingStrategy.HYBRID
    processing_status: Optional[str] = "pending"
    processing_progress: Optional[int] = 0
    processing_message: Optional[str] = None
    file_size: Optional[int] = 0
    file_type: Optional[str] = None
    document_type: Optional[str] = None
    brief_summary: Optional[str] = None
    ocr_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Additional properties to return via API
class Document(DocumentInDBBase):
    tags: List[Tag] = []

# Document with summary
class DocumentWithSummary(Document):
    summary: Optional[str] = None

# Document summary schema
class DocumentSummaryBase(BaseModel):
    document_id: int
    summary_text: str
    model_used: Optional[str] = None
    summary_type: Optional[str] = "comprehensive"

# Properties to receive via API on creation
class DocumentSummaryCreate(DocumentSummaryBase):
    pass

# Properties shared by models stored in DB
class DocumentSummaryInDBBase(DocumentSummaryBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Additional properties to return via API
class DocumentSummary(DocumentSummaryInDBBase):
    pass