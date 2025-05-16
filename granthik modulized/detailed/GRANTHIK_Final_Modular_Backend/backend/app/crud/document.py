from typing import Any, Dict, Optional, Union, List

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.models import Document, DocumentSummary, Group, User, Tag
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentSummaryCreate

def get_document(db: Session, id: int) -> Optional[Document]:
    return db.query(Document).filter(Document.id == id).first()

def get_document_by_file_id(db: Session, file_id: str) -> Optional[Document]:
    return db.query(Document).filter(Document.file_id == file_id).first()

def get_documents(db: Session, skip: int = 0, limit: int = 100) -> List[Document]:
    return db.query(Document).offset(skip).limit(limit).all()

def get_user_documents(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Document]:
    return db.query(Document).filter(Document.owner_id == user_id).offset(skip).limit(limit).all()

def get_public_documents(db: Session, skip: int = 0, limit: int = 100) -> List[Document]:
    return db.query(Document).filter(Document.is_public == True).offset(skip).limit(limit).all()

def get_group_documents(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Document]:
    # Get all groups the user belongs to
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
    
    group_ids = [group.id for group in user.groups]
    if not group_ids:
        return []
    
    # Get all documents shared with these groups
    documents = []
    for group_id in group_ids:
        group = db.query(Group).filter(Group.id == group_id).first()
        if group:
            documents.extend(group.documents)
    
    # Remove duplicates and apply pagination
    unique_docs = list({doc.id: doc for doc in documents}.values())
    start = min(skip, len(unique_docs))
    end = min(skip + limit, len(unique_docs))
    return unique_docs[start:end]

def create_document(db: Session, obj_in: DocumentCreate, owner_id: int) -> Document:
    db_obj = Document(
        filename=obj_in.filename,
        file_path=obj_in.file_path,
        file_id=obj_in.file_id,
        owner_id=owner_id,
        is_public=obj_in.is_public,
        chunk_count=obj_in.chunk_count,
        chunk_size=obj_in.chunk_size,
        chunk_overlap=obj_in.chunk_overlap,
        chunking_strategy=obj_in.chunking_strategy.value if obj_in.chunking_strategy else "hybrid"
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    # Add document to groups if specified
    if obj_in.group_ids:
        for group_id in obj_in.group_ids:
            group = db.query(Group).filter(Group.id == group_id).first()
            if group:
                db_obj.groups.append(group)
    
    # Add document to tags if specified
    if obj_in.tag_ids:
        for tag_id in obj_in.tag_ids:
            tag = db.query(Tag).filter(Tag.id == tag_id).first()
            if tag:
                db_obj.tags.append(tag)
    
    db.commit()
    db.refresh(db_obj)
    
    return db_obj

def update_document(
    db: Session, *, db_obj: Document, obj_in: Union[DocumentUpdate, Dict[str, Any]]
) -> Document:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    # Handle group_ids and tag_ids separately
    group_ids = update_data.pop("group_ids", None)
    tag_ids = update_data.pop("tag_ids", None)
    
    for field in update_data:
        if field in update_data:
            setattr(db_obj, field, update_data[field])
    
    # Update groups if specified
    if group_ids is not None:
        # Clear existing groups
        db_obj.groups = []
        
        # Add new groups
        for group_id in group_ids:
            group = db.query(Group).filter(Group.id == group_id).first()
            if group:
                db_obj.groups.append(group)
    
    # Update tags if specified
    if tag_ids is not None:
        # Clear existing tags
        db_obj.tags = []
        
        # Add new tags
        for tag_id in tag_ids:
            tag = db.query(Tag).filter(Tag.id == tag_id).first()
            if tag:
                db_obj.tags.append(tag)
    
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def delete_document(db: Session, *, id: int) -> Document:
    obj = db.query(Document).get(id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj

def create_document_summary(db: Session, obj_in: DocumentSummaryCreate) -> DocumentSummary:
    db_obj = DocumentSummary(
        document_id=obj_in.document_id,
        summary_text=obj_in.summary_text,
        model_used=obj_in.model_used,
        summary_type=obj_in.summary_type,
        created_by_id=getattr(obj_in, 'created_by_id', None)
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_document_summaries(db: Session, document_id: int) -> List[DocumentSummary]:
    return db.query(DocumentSummary).filter(DocumentSummary.document_id == document_id).all()

def get_document_summary(db: Session, id: int) -> Optional[DocumentSummary]:
    return db.query(DocumentSummary).filter(DocumentSummary.id == id).first()

def delete_document_summary(db: Session, *, id: int) -> DocumentSummary:
    obj = db.query(DocumentSummary).get(id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj

def add_document_to_group(db: Session, *, document_id: int, group_id: int) -> Optional[Document]:
    document = get_document(db, id=document_id)
    group = db.query(Group).filter(Group.id == group_id).first()
    
    if not document or not group:
        return None
    
    if group not in document.groups:
        document.groups.append(group)
        db.commit()
        db.refresh(document)
    
    return document

def remove_document_from_group(db: Session, *, document_id: int, group_id: int) -> Optional[Document]:
    document = get_document(db, id=document_id)
    group = db.query(Group).filter(Group.id == group_id).first()
    
    if not document or not group:
        return None
    
    if group in document.groups:
        document.groups.remove(group)
        db.commit()
        db.refresh(document)
    
    return document