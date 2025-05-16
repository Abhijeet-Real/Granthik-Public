from sqlalchemy.orm import Session
from . import models, schema

def create_document(db: Session, doc: schema.DocumentCreate):
    db_doc = models.Document(**doc.dict())
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

def get_document(db: Session, doc_id: int):
    return db.query(models.Document).filter(models.Document.id == doc_id).first()

def list_documents(db: Session):
    return db.query(models.Document).all()