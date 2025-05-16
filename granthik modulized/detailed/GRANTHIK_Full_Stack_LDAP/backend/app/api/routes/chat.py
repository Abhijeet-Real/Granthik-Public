from typing import Any, List, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.chat import ChatQuery, ChatResponse, ChatHistoryItem
from app.crud import chat as chat_crud, document as document_crud
from app.api.deps import get_current_user, get_db
from app.services.llm import llm_query
from app.services.vector_store import get_vectorstore
from app.services.models import get_available_models, save_models
from app.services.rag import RAGService
from app.core.config import settings

from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOllama

router = APIRouter()

@router.post("/chat/query", response_model=ChatResponse)
def query_chat(
    *,
    db: Session = Depends(get_db),
    query_in: ChatQuery,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Query the chat system
    """
    model = query_in.model or settings.DEFAULT_MODEL
    
    try:
        if query_in.mode == "RAG":
            import logging
            logger = logging.getLogger("uvicorn")
            logger.info(f"Processing RAG query: {query_in.query}")
            
            # Get file_ids for the specified document_ids
            file_ids = []
            if query_in.document_ids:
                for doc_id in query_in.document_ids:
                    doc = document_crud.get_document(db, id=doc_id)
                    if doc:
                        # Check if user has access to this document
                        if doc.owner_id == current_user.id or doc.is_public:
                            file_ids.append(doc.file_id)
                        else:
                            # Check if document is shared with any of user's groups
                            user_group_ids = [group.id for group in current_user.groups]
                            document_group_ids = [group.id for group in doc.groups]
                            if any(g_id in user_group_ids for g_id in document_group_ids):
                                file_ids.append(doc.file_id)
            
            # Prepare date range if specified
            date_range = None
            if query_in.date_from or query_in.date_to:
                date_range = {}
                if query_in.date_from:
                    date_range["start"] = query_in.date_from.isoformat()
                if query_in.date_to:
                    date_range["end"] = query_in.date_to.isoformat()
            
            # Use custom top_k if provided, otherwise use default
            top_k = query_in.top_k or settings.TOP_K
            
            # Initialize RAG service
            rag_service = RAGService(model=model)
            
            # Process query
            result = rag_service.query(
                query=query_in.query,
                file_ids=file_ids if file_ids else None,
                top_k=top_k,
                date_range=date_range,
                retrieval_strategy="hybrid"  # Use hybrid retrieval by default
            )
            
            # Extract answer and sources
            answer = result["answer"]
            sources = result["sources"]
            
            # Format sources for response and add document_id
            formatted_sources = []
            for source in sources:
                # Find document ID from file_id
                document_id = None
                if "file_id" in source["metadata"]:
                    try:
                        document = document_crud.get_document_by_file_id(db, file_id=source["metadata"]["file_id"])
                        if document:
                            document_id = document.id
                    except Exception as e:
                        logger.error(f"Error finding document_id: {str(e)}")
                
                # Add document_id to metadata
                metadata = source["metadata"].copy()
                if document_id:
                    metadata["document_id"] = document_id
                
                formatted_sources.append({
                    "content": source["content"],
                    "metadata": metadata
                })
            
            # Save to chat history
            chat_crud.create_chat_history(
                db=db,
                user_id=current_user.id,
                query=query_in.query,
                answer=answer,
                model_used=model
            )
            
            return {
                "answer": answer,
                "sources": formatted_sources
            }
        else:
            # General mode - direct LLM query
            answer = llm_query(model, query_in.query)
            
            # Save to chat history
            chat_crud.create_chat_history(
                db=db,
                user_id=current_user.id,
                query=query_in.query,
                answer=answer,
                model_used=model
            )
            
            return {
                "answer": answer,
                "sources": None
            }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat query: {str(e)}",
        )

@router.get("/chat/history", response_model=List[ChatHistoryItem])
def get_chat_history(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get user's chat history
    """
    history = chat_crud.get_user_chat_history(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return history

@router.delete("/chat/history", response_model=dict)
def clear_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Clear user's chat history
    """
    count = chat_crud.clear_user_chat_history(db=db, user_id=current_user.id)
    return {"deleted": count}

@router.get("/models", response_model=List[Dict[str, Any]])
def get_models(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get available LLM models
    """
    return get_available_models()

@router.post("/models", response_model=Dict[str, Any])
def update_models(
    models: List[Dict[str, Any]],
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update available LLM models (admin only)
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    success = save_models(models)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save models configuration"
        )
    
    return {"success": True, "message": "Models updated successfully"}