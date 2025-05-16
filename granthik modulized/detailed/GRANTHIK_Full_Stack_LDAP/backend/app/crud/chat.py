from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models import ChatHistory
from app.schemas.chat import ChatHistoryCreate

def create_chat_history(
    db: Session, 
    user_id: int, 
    query: str, 
    answer: str, 
    model_used: str
) -> ChatHistory:
    """
    Create a new chat history entry
    """
    db_obj = ChatHistory(
        user_id=user_id,
        query=query,
        answer=answer,
        model_used=model_used
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_chat_history(db: Session, id: int) -> Optional[ChatHistory]:
    """
    Get a specific chat history entry by ID
    """
    return db.query(ChatHistory).filter(ChatHistory.id == id).first()

def get_user_chat_history(
    db: Session, 
    user_id: int, 
    skip: int = 0, 
    limit: int = 100
) -> List[ChatHistory]:
    """
    Get chat history for a specific user
    """
    return db.query(ChatHistory)\
        .filter(ChatHistory.user_id == user_id)\
        .order_by(ChatHistory.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

def delete_chat_history(db: Session, id: int) -> Optional[ChatHistory]:
    """
    Delete a specific chat history entry
    """
    obj = db.query(ChatHistory).get(id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj

def clear_user_chat_history(db: Session, user_id: int) -> int:
    """
    Clear all chat history for a specific user
    
    Returns:
        Number of entries deleted
    """
    result = db.query(ChatHistory).filter(ChatHistory.user_id == user_id).delete()
    db.commit()
    return result