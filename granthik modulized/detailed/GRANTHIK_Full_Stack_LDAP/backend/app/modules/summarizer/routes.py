from fastapi import APIRouter
from pydantic import BaseModel
from .service import summarize_from_ocr

router = APIRouter(prefix="/summarize", tags=["Summarizer"])

class SummaryRequest(BaseModel):
    ocr_file_path: str
    mode: str = "brief"  # options: brief, detailed, executive

@router.post("/")
def summarize_endpoint(req: SummaryRequest):
    summary = summarize_from_ocr(req.ocr_file_path, req.mode)
    return {"summary": summary}