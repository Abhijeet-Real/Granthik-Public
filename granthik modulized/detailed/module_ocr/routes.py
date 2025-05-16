from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .service import process_file_with_ocr
import os

router = APIRouter(prefix="/ocr", tags=["OCR"])

class OCRRequest(BaseModel):
    filepath: str

@router.post("/process")
def ocr_process(req: OCRRequest):
    if not os.path.exists(req.filepath):
        raise HTTPException(status_code=404, detail="File not found.")
    result = process_file_with_ocr(req.filepath)
    return {"status": "success", "result": result}