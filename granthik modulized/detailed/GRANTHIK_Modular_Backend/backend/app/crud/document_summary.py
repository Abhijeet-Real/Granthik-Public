from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.models import DocumentSummary

def delete_document_summaries(db: Session, document_id: int) -> int:
    """
    Delete all summaries for a document
    
    Args:
        db: Database session
        document_id: ID of the document
        
    Returns:
        Number of summaries deleted
    """
    result = db.query(DocumentSummary).filter(DocumentSummary.document_id == document_id).delete()
    db.commit()
    return result

def get_document_summary(db: Session, summary_id: int) -> Optional[DocumentSummary]:
    """
    Get a document summary by ID
    
    Args:
        db: Database session
        summary_id: ID of the summary
        
    Returns:
        DocumentSummary object or None if not found
    """
    return db.query(DocumentSummary).filter(DocumentSummary.id == summary_id).first()

def get_document_summaries(db: Session, document_id: int) -> List[DocumentSummary]:
    """
    Get all summaries for a document
    
    Args:
        db: Database session
        document_id: ID of the document
        
    Returns:
        List of DocumentSummary objects
    """
    return db.query(DocumentSummary).filter(DocumentSummary.document_id == document_id).all()

def get_document_summaries_by_type(db: Session, document_id: int, summary_type: str) -> List[DocumentSummary]:
    """
    Get all summaries of a specific type for a document
    
    Args:
        db: Database session
        document_id: ID of the document
        summary_type: Type of summary (comprehensive, concise, key_points)
        
    Returns:
        List of DocumentSummary objects
    """
    return db.query(DocumentSummary).filter(
        DocumentSummary.document_id == document_id,
        DocumentSummary.summary_type == summary_type
    ).all()

def delete_document_summary(db: Session, summary_id: int) -> bool:
    """
    Delete a specific document summary
    
    Args:
        db: Database session
        summary_id: ID of the summary to delete
        
    Returns:
        True if deleted, False if not found
    """
    summary = db.query(DocumentSummary).filter(DocumentSummary.id == summary_id).first()
    if summary:
        db.delete(summary)
        db.commit()
        return True
    return False