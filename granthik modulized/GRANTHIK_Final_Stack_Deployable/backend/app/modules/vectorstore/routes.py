from fastapi import APIRouter
from pydantic import BaseModel
from .service import create_vectorstore, query_vectorstore

router = APIRouter(prefix="/vectorstore", tags=["Vectorstore"])

class StoreRequest(BaseModel):
    docs: list[str]
    metadatas: list[dict] = []

class QueryRequest(BaseModel):
    query: str
    k: int = 5

@router.post("/store")
def store_docs(req: StoreRequest):
    return create_vectorstore(req.docs, req.metadatas)

@router.post("/query")
def query_docs(req: QueryRequest):
    results = query_vectorstore(req.query, req.k)
    return {"results": [r.page_content for r in results]}