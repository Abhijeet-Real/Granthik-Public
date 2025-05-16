from fastapi import APIRouter
from pydantic import BaseModel
from .service import chunk_text

router = APIRouter(prefix="/chunk", tags=["Chunker"])

class ChunkRequest(BaseModel):
    text: str
    chunk_size: int = 1000
    chunk_overlap: int = 200

@router.post("/")
def chunk_route(req: ChunkRequest):
    chunks = chunk_text(req.text, req.chunk_size, req.chunk_overlap)
    return {"total_chunks": len(chunks), "chunks": chunks}