import os
from typing import List, Dict, Any
from datetime import datetime

import chromadb
from chromadb import PersistentClient
from chromadb.config import Settings, DEFAULT_TENANT, DEFAULT_DATABASE
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings

# Initialize ChromaDB client
os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
chroma_settings = Settings(anonymized_telemetry=False)
chroma_client = PersistentClient(
    path=settings.VECTOR_DB_PATH,
    settings=chroma_settings,
    tenant=DEFAULT_TENANT,
    database=DEFAULT_DATABASE
)

# Get or create collection
def get_collection():
    return chroma_client.get_or_create_collection(name="docs")

# Get vector store
def get_vectorstore():
    import logging
    import os
    from langchain_community.embeddings import HuggingFaceEmbeddings
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Using Ollama URL: {settings.OLLAMA_URL}")
    
    # Always try to use Ollama with nomic-embed-text first
    try:
        # Extract base URL without the /api/generate part
        base_url = settings.OLLAMA_URL
        if base_url.endswith("/api/generate"):
            base_url = base_url.replace("/api/generate", "")
        elif base_url.endswith("/generate"):
            base_url = base_url.replace("/generate", "")
        elif base_url.endswith("/api"):
            base_url = base_url.replace("/api", "")
            
        logger.info(f"Using Ollama base URL for embeddings: {base_url}")
        
        # Use nomic-embed-text model as specified
        embedding_fn = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=base_url,
            show_progress=True
        )
        logger.info("Successfully initialized Ollama embeddings with nomic-embed-text model")
        
        # Test the embeddings with a simple string to verify it works
        try:
            test_embedding = embedding_fn.embed_query("Test embedding")
            logger.info(f"Embedding test successful, dimension: {len(test_embedding)}")
        except Exception as test_error:
            logger.warning(f"Embedding test failed: {str(test_error)}. Will try fallback if needed.")
            
        return Chroma(
            client=chroma_client,
            collection_name="docs",
            embedding_function=embedding_fn
        )
        
    except Exception as e:
        logger.error(f"Ollama embeddings error: {str(e)}. Using fallback embeddings.")
        
        # If Ollama is not available, use HuggingFace embeddings as fallback
        try:
            # Use a small, efficient model for embeddings
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            
            # Create cache directory if it doesn't exist
            cache_dir = os.path.join(settings.UPLOAD_DIR, "hf_cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            embedding_fn = HuggingFaceEmbeddings(
                model_name=model_name,
                cache_folder=cache_dir,
                encode_kwargs={"normalize_embeddings": True}
            )
            logger.info(f"Using HuggingFace embeddings with model: {model_name}")
            
            return Chroma(
                client=chroma_client,
                collection_name="docs",
                embedding_function=embedding_fn
            )
            
        except Exception as hf_error:
            # If HuggingFace embeddings fail, use fake embeddings as last resort
            logger.error(f"HuggingFace embeddings error: {str(hf_error)}. Using fallback embeddings.")
            from langchain.embeddings.fake import FakeEmbeddings
            embedding_fn = FakeEmbeddings(size=1536)  # Use fake embeddings as fallback
            logger.info("Using fake embeddings for vector store")
            
            return Chroma(
                client=chroma_client,
                collection_name="docs",
                embedding_function=embedding_fn
            )

def insert_chunks(chunks: List[Dict[str, Any]], file_id: str, filename: str) -> int:
    """
    Insert document chunks into the vector store
    
    Args:
        chunks: List of text chunks from OCR
        file_id: Unique identifier for the file
        filename: Name of the file
    
    Returns:
        Number of chunks inserted
    """
    import logging
    import gc
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Inserting {len(chunks)} chunks into vector store for file: {filename}")
    
    vectorstore = get_vectorstore()
    ts = datetime.utcnow()
    ts_iso = ts.isoformat()
    ts_date = ts.date().isoformat()
    
    # Prepare all chunks
    all_texts, all_metas, all_ids = [], [], []
    for idx, chunk in enumerate(chunks):
        txt = chunk.get("text", "").strip()
        if txt:
            all_texts.append(txt)
            all_metas.append({
                "file_id": file_id,
                "filename": filename,
                "chunk_index": idx,
                "timestamp": ts_iso,
                "date": ts_date,
                "content_preview": txt[:100] if len(txt) > 100 else txt  # Add content preview for metadata search
            })
            all_ids.append(f"{file_id}_{idx}")
    
    # Process in smaller batches to prevent memory issues
    batch_size = 20  # Smaller batch size to prevent browser crashes
    total_inserted = 0
    
    for i in range(0, len(all_texts), batch_size):
        batch_end = min(i + batch_size, len(all_texts))
        batch_texts = all_texts[i:batch_end]
        batch_metas = all_metas[i:batch_end]
        batch_ids = all_ids[i:batch_end]
        
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(all_texts) + batch_size - 1)//batch_size}: {len(batch_texts)} chunks")
        
        try:
            # Add texts to vector store
            vectorstore.add_texts(batch_texts, metadatas=batch_metas, ids=batch_ids)
            total_inserted += len(batch_texts)
            
            # Force garbage collection after each batch
            gc.collect()
            
            logger.info(f"Successfully inserted batch {i//batch_size + 1}, total inserted: {total_inserted}")
        except Exception as e:
            logger.error(f"Error inserting batch {i//batch_size + 1}: {str(e)}")
            # Continue with next batch even if this one fails
    
    logger.info(f"Completed inserting chunks: {total_inserted} out of {len(all_texts)} inserted")
    return total_inserted

def fetch_chunks(file_id: str) -> tuple:
    """
    Fetch chunks for a specific file
    
    Args:
        file_id: Unique identifier for the file
    
    Returns:
        Tuple of (documents, metadatas)
    """
    collection = get_collection()
    result = collection.get(where={"file_id": file_id}, include=["documents", "metadatas"])
    return result.get("documents", []), result.get("metadatas", [])

def delete_file_chunks(file_id: str) -> None:
    """
    Delete all chunks for a specific file
    
    Args:
        file_id: Unique identifier for the file
    """
    collection = get_collection()
    collection.delete(where={"file_id": file_id})

def search_chunks(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for document chunks matching a query
    
    Args:
        query: Search query
        limit: Maximum number of results to return
    
    Returns:
        List of matching document chunks with metadata
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Searching for: {query}")
    
    vectorstore = get_vectorstore()
    
    try:
        results = vectorstore.similarity_search_with_relevance_scores(
            query, 
            k=limit
        )
        
        # Format results
        formatted_results = []
        for doc, score in results:
            if score > 0.3:  # Only include results with reasonable relevance
                formatted_results.append({
                    "text": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": score
                })
        
        logger.info(f"Found {len(formatted_results)} relevant results")
        return formatted_results
    except Exception as e:
        logger.error(f"Error searching vector store: {str(e)}")
        return []