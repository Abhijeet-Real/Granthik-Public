from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, date

# Chat query request
class ChatQuery(BaseModel):
    query: str
    model: Optional[str] = None
    document_ids: Optional[List[int]] = None
    mode: str = "RAG"  # "RAG" or "General"
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    top_k: Optional[int] = None  # Number of chunks to retrieve, defaults to settings.TOP_K

# Chat response
class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[Dict[str, Any]]] = None

# Chat history create schema
class ChatHistoryCreate(BaseModel):
    user_id: int
    query: str
    answer: str
    model_used: Optional[str] = None

# Chat history item
class ChatHistoryItem(BaseModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    query: str
    answer: str
    model_used: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True