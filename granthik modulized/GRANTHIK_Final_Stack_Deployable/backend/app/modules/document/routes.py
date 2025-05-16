from fastapi import APIRouter, Depends, UploadFile, Form
from sqlalchemy.orm import Session
from app.db.session import get_db
from . import crud, schema, service

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/", response_model=schema.DocumentOut)
def upload_document(file: UploadFile, uploaded_by: str = Form(...), db: Session = Depends(get_db)):
    filepath = service.save_file(file)
    new_doc = schema.DocumentCreate(filename=file.filename, filepath=filepath, uploaded_by=uploaded_by)
    return crud.create_document(db, new_doc)

@router.get("/{doc_id}", response_model=schema.DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    return crud.get_document(db, doc_id)

@router.get("/", response_model=list[schema.DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return crud.list_documents(db)