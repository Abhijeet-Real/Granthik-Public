from fastapi import APIRouter
from pydantic import BaseModel
from .service import answer_with_rag, answer_with_general_llm

router = APIRouter(prefix="/chat", tags=["Chatbot"])

class Query(BaseModel):
    question: str

@router.post("/rag")
def chat_rag(req: Query):
    answer = answer_with_rag(req.question)
    return {"response": answer}

@router.post("/general")
def chat_general(req: Query):
    answer = answer_with_general_llm(req.question)
    return {"response": answer}