from typing import Any, List, Optional
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.models import User
from app.schemas.document import Document, DocumentCreate, DocumentUpdate, DocumentSummaryCreate, DocumentSummary
from app.crud import document as document_crud
from app.api.deps import get_current_user, get_db
from app.services.ocr import ocr_parse
from app.services.vector_store import insert_chunks, delete_file_chunks
from app.services.llm import llm_query
from app.services.export import export_to_docx
from app.services.document_processor import process_document, ChunkingStrategy, extract_text_from_file
from app.services.document_analyzer import analyze_document_structure, get_chunking_recommendations
from app.core.config import settings

router = APIRouter()

def generate_fallback_summary(filename: str, summary_type: str) -> str:
    """
    Generate a fallback summary when LLM is not available
    
    Args:
        filename: The name of the document
        summary_type: The type of summary requested
        
    Returns:
        A fallback summary message
    """
    if summary_type == "comprehensive":
        return f"""## Fallback Summary - LLM Service Unavailable

This is a fallback comprehensive summary for **{filename}**. 

The document summarization service is currently unavailable. Please try again later.

### What You Would Normally See:
- A detailed overview of the document's main content
- All major points and arguments
- Important details and supporting information
- The document's structure and organization

### Next Steps:
- Try refreshing the page
- Check if the LLM service is running
- Try again in a few minutes
"""
    elif summary_type == "concise":
        return f"""## Fallback Concise Summary - LLM Service Unavailable

This is a fallback concise summary for **{filename}**. 

The document summarization service is currently unavailable. Please try again later.

### What You Would Normally See:
- A brief overview of the document's main content
- Only the most important information
- A summary about 20-25% the length of the original document

### Next Steps:
- Try refreshing the page
- Check if the LLM service is running
- Try again in a few minutes
"""
    elif summary_type == "key_points":
        return f"""## Fallback Key Points - LLM Service Unavailable

This is a fallback key points summary for **{filename}**. 

The document summarization service is currently unavailable. Please try again later.

### What You Would Normally See:
- A bullet-point list of the main takeaways
- Actionable insights from the document
- Direct and concise points
- Organized sections with clear headings

### Next Steps:
- Try refreshing the page
- Check if the LLM service is running
- Try again in a few minutes
"""
    else:
        return f"""## Fallback Summary - LLM Service Unavailable

This is a fallback summary for **{filename}**. 

The document summarization service is currently unavailable. Please try again later.

### Next Steps:
- Try refreshing the page
- Check if the LLM service is running
- Try again in a few minutes
"""

@router.post("/documents/bulk-upload", response_model=List[Document])
async def bulk_upload_documents(
    *,
    db: Session = Depends(get_db),
    files: List[UploadFile] = File(...),
    ocr_languages: str = Form("eng"),
    group_ids: Optional[List[int]] = Form(None),
    is_public: bool = Form(False),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload and process multiple documents with OCR
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Starting bulk document upload: {len(files)} files")
    
    # Create upload directory if it doesn't exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    uploaded_documents = []
    
    for file in files:
        try:
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            logger.info(f"Processing file: {file.filename} with ID: {file_id}")
            
            # Save file to disk
            file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{file.filename}")
            
            file_content = await file.read()
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Process with OCR
            logger.info(f"Processing with OCR, languages: {ocr_languages}")
            langs = ocr_languages.split(",")
            chunks = ocr_parse(file_content, file.filename, langs)
            logger.info(f"OCR processing complete, got {len(chunks)} chunks")
            
            # Insert chunks into vector store
            logger.info(f"Inserting chunks into vector store")
            chunk_count = insert_chunks(chunks, file_id, file.filename)
            logger.info(f"Inserted {chunk_count} chunks into vector store")
            
            # Create document record
            document_in = DocumentCreate(
                filename=file.filename,
                file_path=file_path,
                file_id=file_id,
                is_public=is_public,
                chunk_count=chunk_count,
                group_ids=group_ids or []
            )
            
            document = document_crud.create_document(
                db=db, 
                obj_in=document_in, 
                owner_id=current_user.id
            )
            
            uploaded_documents.append(document)
            
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {str(e)}")
            # Continue with next file instead of failing the entire batch
            continue
    
    if not uploaded_documents:
        raise HTTPException(
            status_code=500,
            detail="Failed to process any of the uploaded files"
        )
    
    return uploaded_documents

@router.post("/documents/upload", response_model=Document)
async def upload_document(
    *,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    ocr_languages: str = Form("eng"),
    group_ids: Optional[List[int]] = Form(None),
    is_public: bool = Form(False),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    chunking_strategy: ChunkingStrategy = Form(ChunkingStrategy.HYBRID),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload and process a document with OCR
    
    Args:
        file: The document file to upload
        ocr_languages: Comma-separated list of language codes for OCR
        group_ids: List of group IDs to share the document with
        is_public: Whether the document is publicly accessible
        chunk_size: Size of text chunks in characters (0 to use default chunking)
        chunk_overlap: Overlap between chunks in characters
        chunking_strategy: Strategy to use for chunking (fixed_size, paragraph, sentence, hybrid)
    """
    import logging
    import gc
    import psutil
    import traceback
    from app.services.document_processor import extract_text_from_file
    
    logger = logging.getLogger("uvicorn")
    
    # Log memory usage at start
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logger.info(f"Memory usage at start: {memory_info.rss / 1024 / 1024:.2f} MB")
    
    logger.info(f"Starting document upload: {file.filename}, strategy={chunking_strategy}, chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    
    # Validate input parameters
    if chunk_size <= 0:
        chunk_size = 1000
        logger.warning(f"Invalid chunk_size provided, using default: {chunk_size}")
    
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        chunk_overlap = min(200, chunk_size // 5)
        logger.warning(f"Invalid chunk_overlap provided, using default: {chunk_overlap}")
    
    # Create upload directory if it doesn't exist and ensure proper permissions
    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        # Ensure directory has proper permissions (readable and writable)
        os.chmod(settings.UPLOAD_DIR, 0o755)
        logger.info(f"Upload directory: {settings.UPLOAD_DIR}")
    except Exception as dir_error:
        logger.error(f"Error creating or setting permissions on upload directory: {str(dir_error)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Server configuration error: Unable to access upload directory"
        )
    
    # Get max upload size from settings (default to 100MB if not set)
    max_upload_size = getattr(settings, "MAX_UPLOAD_SIZE", 100 * 1024 * 1024)
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    logger.info(f"Generated file ID: {file_id}")
    
    # Sanitize filename to prevent path traversal and security issues
    safe_filename = os.path.basename(file.filename).replace(" ", "_")
    # Remove any potentially dangerous characters
    safe_filename = ''.join(c for c in safe_filename if c.isalnum() or c in '._-')
    if not safe_filename:
        safe_filename = f"document_{file_id}.bin"
    
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{safe_filename}")
    logger.info(f"Saving file to: {file_path}")
    
    try:
        # Read file in chunks to avoid memory issues with large files
        file_size = 0
        with open(file_path, "wb") as f:
            # Read and write in 1MB chunks
            chunk_size_bytes = 1024 * 1024
            while True:
                chunk = await file.read(chunk_size_bytes)
                if not chunk:
                    break
                file_size += len(chunk)
                
                # Check if file size exceeds the maximum allowed
                if file_size > max_upload_size:
                    # Close and delete the partial file
                    f.close()
                    os.remove(file_path)
                    logger.warning(f"File size exceeds maximum allowed size of {max_upload_size/1024/1024:.1f}MB")
                    raise HTTPException(
                        status_code=413,
                        detail=f"File size exceeds maximum allowed size of {max_upload_size/1024/1024:.1f}MB"
                    )
                
                f.write(chunk)
        
        # Ensure file has proper permissions
        os.chmod(file_path, 0o644)
        logger.info(f"File saved to disk with proper permissions, size: {file_size} bytes")
        
        # Log memory usage after file save
        memory_info = process.memory_info()
        logger.info(f"Memory usage after file save: {memory_info.rss / 1024 / 1024:.2f} MB")
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        logger.error(traceback.format_exc())
        # Try to clean up if file was partially created
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
    
    try:
        # Process document with enhanced processor
        logger.info(f"Processing document with strategy: {chunking_strategy}")
        langs = [lang.strip() for lang in ocr_languages.split(",") if lang.strip()]
        if not langs:
            langs = ["eng"]  # Default to English if no valid languages provided
        
        # For very large files, use a more memory-efficient chunking strategy
        if file_size > 5 * 1024 * 1024:  # 5MB
            logger.info(f"Large file detected ({file_size/1024/1024:.2f}MB), using paragraph chunking strategy")
            local_chunking_strategy = ChunkingStrategy.PARAGRAPH
            local_chunk_size = min(chunk_size, 500)  # Smaller chunks for large files
        else:
            local_chunking_strategy = chunking_strategy
            local_chunk_size = chunk_size
        
        # Process in a more memory-efficient way
        logger.info(f"Starting document processing with memory-efficient approach")
        
        # Read file for processing
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # First, extract metadata only
            try:
                doc_metadata = extract_metadata(file_content, file.filename)
                logger.info(f"Extracted metadata: {doc_metadata}")
            except Exception as meta_error:
                logger.warning(f"Error extracting metadata: {str(meta_error)}")
                doc_metadata = {"filename": file.filename}
            
            # Log memory usage before OCR
            memory_info = process.memory_info()
            logger.info(f"Memory usage before OCR: {memory_info.rss / 1024 / 1024:.2f} MB")
            
            # Process document with OCR
            try:
                chunks, _ = process_document(
                    file_content,
                    file.filename, 
                    langs, 
                    local_chunk_size, 
                    chunk_overlap,
                    local_chunking_strategy
                )
                
                # Free up memory immediately
                del file_content
                gc.collect()
                
                logger.info(f"Document processing complete, got {len(chunks)} chunks")
                
                # Log memory usage after OCR
                memory_info = process.memory_info()
                logger.info(f"Memory usage after OCR: {memory_info.rss / 1024 / 1024:.2f} MB")
                
                # Insert chunks into vector store in batches
                logger.info(f"Inserting chunks into vector store in batches")
                chunk_count = insert_chunks(chunks, file_id, file.filename)
                
                # Free up memory again
                del chunks
                gc.collect()
                
                logger.info(f"Inserted {chunk_count} chunks into vector store")
                
                # Log memory usage after vector store insertion
                memory_info = process.memory_info()
                logger.info(f"Memory usage after vector store insertion: {memory_info.rss / 1024 / 1024:.2f} MB")
                
            except Exception as proc_error:
                logger.error(f"Error in document processing: {str(proc_error)}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error processing document: {str(proc_error)}"
                )
                
        except Exception as file_read_error:
            logger.error(f"Error reading file for processing: {str(file_read_error)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500, 
                detail=f"Error reading file for processing: {str(file_read_error)}"
            )
        
        # Create document record
        logger.info(f"Creating document record in database")
        document_in = DocumentCreate(
            filename=file.filename,
            file_path=file_path,
            file_id=file_id,
            is_public=is_public,
            chunk_count=chunk_count,
            group_ids=group_ids or [],
            chunk_size=local_chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_strategy=local_chunking_strategy,
            processing_status="completed",
            processing_progress=100,
            processing_message="Document processed successfully"
        )
        
        logger.info(f"Document data: {document_in}")
        
        document = document_crud.create_document(
            db=db,
            obj_in=document_in,
            owner_id=current_user.id
        )
        
        # Force garbage collection
        gc.collect()
        
        logger.info(f"Document created successfully with ID: {document.id}")
        return document
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error processing document: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Clean up file if processing fails
        if os.path.exists(file_path):
            logger.info(f"Cleaning up file: {file_path}")
            os.remove(file_path)
        
        # Force garbage collection
        gc.collect()
            
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}",
        )

@router.post("/documents/upload/bulk", response_model=List[Document])
async def upload_multiple_documents(
    *,
    db: Session = Depends(get_db),
    files: List[UploadFile] = File(...),
    ocr_languages: str = Form("eng"),
    group_ids: Optional[List[int]] = Form(None),
    is_public: bool = Form(False),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    chunking_strategy: ChunkingStrategy = Form(ChunkingStrategy.HYBRID),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload and process multiple documents with OCR
    
    Args:
        files: List of document files to upload
        ocr_languages: Comma-separated list of language codes for OCR
        group_ids: List of group IDs to share the documents with
        is_public: Whether the documents are publicly accessible
        chunk_size: Size of text chunks in characters (0 to use default chunking)
        chunk_overlap: Overlap between chunks in characters
        chunking_strategy: Strategy to use for chunking (fixed_size, paragraph, sentence, hybrid)
    """
    import logging
    import gc
    logger = logging.getLogger("uvicorn")
    logger.info(f"Starting bulk document upload: {len(files)} files, strategy={chunking_strategy}, chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    
    # Create upload directory if it doesn't exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Get max upload size from settings (default to 10MB if not set)
    max_upload_size = getattr(settings, "MAX_UPLOAD_SIZE", 10 * 1024 * 1024)
    
    uploaded_documents = []
    
    for file in files:
        try:
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            logger.info(f"Processing file: {file.filename} with ID: {file_id}")
            
            # Save file to disk
            file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{file.filename}")
            
            # Read file content in chunks to avoid memory issues
            file_content = await file.read()
            file_size = len(file_content)
            logger.info(f"Read file content, size: {file_size} bytes")
            
            # Check if file size exceeds the maximum allowed
            if file_size > max_upload_size:
                logger.warning(f"File size ({file_size} bytes) exceeds maximum allowed size ({max_upload_size} bytes)")
                raise HTTPException(
                    status_code=413,
                    detail=f"File size exceeds maximum allowed size of {max_upload_size/1024/1024:.1f}MB"
                )
            
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Process document with enhanced processor
            langs = ocr_languages.split(",")
            
            # For very large files, use a more memory-efficient chunking strategy
            if file_size > 5 * 1024 * 1024:  # 5MB
                logger.info(f"Large file detected, using paragraph chunking strategy")
                local_chunking_strategy = ChunkingStrategy.PARAGRAPH
                local_chunk_size = 500  # Smaller chunks for large files
            else:
                local_chunking_strategy = chunking_strategy
                local_chunk_size = chunk_size
            
            chunks, doc_metadata = process_document(
                file_content, 
                file.filename, 
                langs, 
                local_chunk_size, 
                chunk_overlap,
                local_chunking_strategy
            )
            
            # Free up memory
            del file_content
            gc.collect()
            
            logger.info(f"Document processing complete, got {len(chunks)} chunks")
            logger.info(f"Document metadata: {doc_metadata}")
            
            # Insert chunks into vector store
            chunk_count = insert_chunks(chunks, file_id, file.filename)
            logger.info(f"Inserted {chunk_count} chunks into vector store")
            
            # Get file extension
            file_type = os.path.splitext(file.filename)[1].lower().lstrip('.')
            
            # Extract first few lines of OCR text for quick reference (up to 1000 chars)
            ocr_text = ""
            if chunks and len(chunks) > 0:
                ocr_text = chunks[0].page_content[:1000] if hasattr(chunks[0], 'page_content') else ""
            
            # Determine document type based on content analysis
            document_type = "unknown"
            brief_summary = ""
            
            # Simple heuristic to determine document type
            if ocr_text:
                lower_text = ocr_text.lower()
                if any(term in lower_text for term in ["case", "court", "plaintiff", "defendant", "judgment"]):
                    document_type = "legal_case"
                elif any(term in lower_text for term in ["complaint", "grievance", "allegation"]):
                    document_type = "complaint"
                elif any(term in lower_text for term in ["report", "analysis", "findings"]):
                    document_type = "report"
                elif any(term in lower_text for term in ["letter", "correspondence"]):
                    document_type = "letter"
                elif any(term in lower_text for term in ["policy", "procedure", "guideline"]):
                    document_type = "policy"
                
                # Generate a brief summary from the first few lines
                first_lines = " ".join(ocr_text.split('\n')[:3])
                brief_summary = first_lines[:100] + "..." if len(first_lines) > 100 else first_lines
            
            # Create document record
            document_in = DocumentCreate(
                filename=file.filename,
                file_path=file_path,
                file_id=file_id,
                is_public=is_public,
                chunk_count=chunk_count,
                group_ids=group_ids or [],
                chunk_size=local_chunk_size,
                chunk_overlap=chunk_overlap,
                chunking_strategy=local_chunking_strategy,
                processing_status="completed",
                processing_progress=100,
                processing_message="Document processed successfully",
                file_size=file_size,
                file_type=file_type,
                document_type=document_type,
                brief_summary=brief_summary,
                ocr_text=ocr_text
            )
            
            document = document_crud.create_document(
                db=db,
                obj_in=document_in,
                owner_id=current_user.id
            )
            
            uploaded_documents.append(document)
            logger.info(f"Document created successfully with ID: {document.id}")
            
            # Force garbage collection after each file
            gc.collect()
            
        except Exception as e:
            # Log the error but continue processing other files
            import traceback
            logger.error(f"Error processing document {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Clean up file if processing fails
            if 'file_path' in locals() and os.path.exists(file_path):
                logger.info(f"Cleaning up file: {file_path}")
                os.remove(file_path)
            
            # Force garbage collection
            gc.collect()
    
    if not uploaded_documents:
        raise HTTPException(
            status_code=500,
            detail="Failed to process any of the uploaded documents",
        )
    
    return uploaded_documents

@router.get("/documents", response_model=List[Document])
def get_documents(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get all documents accessible to the current user
    """
    # Get user's own documents
    user_docs = document_crud.get_user_documents(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    
    # Get public documents
    public_docs = document_crud.get_public_documents(
        db=db,
        skip=skip,
        limit=limit
    )
    
    # Get documents shared with user's groups
    group_docs = document_crud.get_group_documents(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    
    # Combine and deduplicate documents
    all_docs = {}
    for doc in user_docs + public_docs + group_docs:
        if doc.id not in all_docs:
            all_docs[doc.id] = doc
    
    # If search term is provided, filter documents by filename
    if search and search.strip():
        search_term = search.lower()
        filtered_docs = {
            doc_id: doc for doc_id, doc in all_docs.items() 
            if search_term in doc.filename.lower()
        }
        return list(filtered_docs.values())
    
    return list(all_docs.values())

@router.get("/documents/search", response_model=List[Document])
def search_documents(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Search for documents by content
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Searching documents with query: {query}")
    
    if not query or not query.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty",
        )
    
    # First get all accessible documents
    # Get user's own documents
    user_docs = document_crud.get_user_documents(
        db=db,
        user_id=current_user.id,
        skip=0,
        limit=1000
    )
    
    # Get public documents
    public_docs = document_crud.get_public_documents(
        db=db,
        skip=0,
        limit=1000
    )
    
    # Get documents shared with user's groups
    group_docs = document_crud.get_group_documents(
        db=db,
        user_id=current_user.id,
        skip=0,
        limit=1000
    )
    
    # Combine and deduplicate documents
    all_docs = {}
    for doc in user_docs + public_docs + group_docs:
        if doc.id not in all_docs:
            all_docs[doc.id] = doc
    
    accessible_document_ids = list(all_docs.keys())
    logger.info(f"User has access to {len(accessible_document_ids)} documents")
    
    # Search in vector database
    from app.services.vector_store import search_chunks
    
    search_results = search_chunks(query, limit=20)
    logger.info(f"Vector search returned {len(search_results)} results")
    
    # Filter results to only include accessible documents
    filtered_results = []
    document_ids = set()
    
    for result in search_results:
        doc_id = result.get("metadata", {}).get("document_id")
        if doc_id and int(doc_id) in all_docs and int(doc_id) not in document_ids:
            document_ids.add(int(doc_id))
            filtered_results.append(all_docs[int(doc_id)])
    
    logger.info(f"Returning {len(filtered_results)} filtered results")
    return filtered_results

@router.get("/documents/{document_id}", response_model=Document)
def get_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get a specific document
    """
    document = document_crud.get_document(db, id=document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )
    
    # Check if user has access to this document
    if document.owner_id != current_user.id and not document.is_public:
        # Check if document is shared with any of user's groups
        user_group_ids = [group.id for group in current_user.groups]
        document_group_ids = [group.id for group in document.groups]
        if not any(g_id in user_group_ids for g_id in document_group_ids):
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions to access this document",
            )
    
    return document

@router.put("/documents/{document_id}", response_model=Document)
def update_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    document_in: DocumentUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a document
    """
    document = document_crud.get_document(db, id=document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )
    
    # Check if user is the owner
    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions to update this document",
        )
    
    # Update document
    document = document_crud.update_document(
        db=db,
        db_obj=document,
        obj_in=document_in
    )
    
    return document

@router.post("/documents/keyword-search", response_model=dict)
async def keyword_search(
    *,
    db: Session = Depends(get_db),
    query: str,
    document_ids: Optional[List[int]] = None,
    case_sensitive: bool = False,
    whole_word: bool = False,
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Search for keywords across all accessible documents
    
    Args:
        query: The keyword or phrase to search for
        document_ids: Optional list of document IDs to search within
        case_sensitive: Whether to perform a case-sensitive search
        whole_word: Whether to match whole words only
        page: Page number for pagination (1-based)
        page_size: Number of results per page
        
    Returns:
        Dictionary containing search results with document and line information
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Performing keyword search for: '{query}'")
    
    try:
        if not query or len(query.strip()) < 2:
            raise HTTPException(
                status_code=400,
                detail="Search query must be at least 2 characters long",
            )
        
        # Get accessible documents
        if document_ids:
            # Filter to specified documents that the user has access to
            documents = []
            for doc_id in document_ids:
                doc = document_crud.get_document(db, id=doc_id)
                if doc and (doc.owner_id == current_user.id or doc.is_public or 
                           any(g in current_user.groups for g in doc.groups)):
                    documents.append(doc)
        else:
            # Get all documents the user has access to
            user_docs = document_crud.get_user_documents(db, user_id=current_user.id)
            public_docs = document_crud.get_public_documents(db)
            group_docs = document_crud.get_group_documents(db, user_id=current_user.id)
            
            # Combine and remove duplicates
            all_docs = user_docs + public_docs + group_docs
            documents = list({doc.id: doc for doc in all_docs}.values())
        
        logger.info(f"Searching across {len(documents)} accessible documents")
        
        # Prepare search results
        all_results = {
            "query": query,
            "total_matches": 0,
            "total_documents": 0,
            "documents": []
        }
        
        # Compile regex pattern based on search options
        import re
        pattern_flags = 0 if case_sensitive else re.IGNORECASE
        pattern_str = r'\b' + re.escape(query) + r'\b' if whole_word else re.escape(query)
        pattern = re.compile(pattern_str, pattern_flags)
        
        # Search each document
        for doc in documents:
            # Try both file path and vector store
            matches = []
            
            # First try file path if available
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    # Read file content
                    with open(doc.file_path, "rb") as f:
                        file_content = f.read()
                    
                    # Extract text
                    text = extract_text_from_file(file_content, doc.filename, ["eng"])
                    
                    # Split into lines
                    lines = text.split('\n')
                    
                    # Search for matches
                    try:
                        for i, line in enumerate(lines):
                            if pattern.search(line):
                                # Get some context (lines before and after)
                                start = max(0, i - 1)
                                end = min(len(lines), i + 2)
                                context = '\n'.join(lines[start:end])
                                
                                matches.append({
                                    "line_number": i + 1,
                                    "line": line.strip(),
                                    "context": context.strip(),
                                    "source": "file"
                                })
                    except Exception as regex_error:
                        logger.error(f"Regex search error in document {doc.id}: {str(regex_error)}")
                except Exception as e:
                    logger.error(f"Error searching document file {doc.id}: {str(e)}")
            
            # If no matches from file or file not available, try vector store
            if not matches and doc.file_id:
                try:
                    from app.services.vector_store import fetch_chunks
                    chunks, metas = fetch_chunks(doc.file_id)
                    
                    if chunks and len(chunks) > 0:
                        for i, chunk in enumerate(chunks):
                            if pattern.search(chunk):
                                # Get metadata if available
                                meta = metas[i] if metas and i < len(metas) else {}
                                chunk_index = meta.get("chunk_index", i) if meta else i
                                
                                matches.append({
                                    "line_number": chunk_index + 1,  # Use chunk index as line number
                                    "line": chunk[:100] + "..." if len(chunk) > 100 else chunk,
                                    "context": chunk,
                                    "source": "vector_store"
                                })
                except Exception as e:
                    logger.error(f"Error searching vector store for document {doc.id}: {str(e)}")
            
            if matches:
                all_results["documents"].append({
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "match_count": len(matches),
                    "matches": matches
                })
                all_results["total_matches"] += len(matches)
        
        # Sort documents by match count (most matches first)
        all_results["documents"].sort(key=lambda x: x["match_count"], reverse=True)
        all_results["total_documents"] = len(all_results["documents"])
        
        # Paginate results
        if page < 1:
            page = 1
            
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        paginated_results = {
            "query": all_results["query"],
            "total_matches": all_results["total_matches"],
            "total_documents": all_results["total_documents"],
            "page": page,
            "page_size": page_size,
            "total_pages": (all_results["total_documents"] + page_size - 1) // page_size,
            "documents": all_results["documents"][start_idx:end_idx]
        }
        
        logger.info(f"Found {all_results['total_matches']} matches across {all_results['total_documents']} documents")
        return paginated_results
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error performing keyword search: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error performing keyword search: {str(e)}",
        )



@router.get("/documents/{document_id}/raw-text", response_model=dict)
async def get_document_raw_text(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get the original raw text extracted from the document before chunking
    
    Args:
        document_id: The ID of the document
        
    Returns:
        Dictionary containing the raw text and metadata
    """
    import logging
    import traceback
    from app.services.document_processor import extract_text_from_file
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Getting raw text for document {document_id}")
    
    try:
        # Get document
        document = document_crud.get_document(db, id=document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )
        
        # Check permissions
        if document.owner_id != current_user.id and not document.is_public:
            # Check if document is shared with any of user's groups
            user_group_ids = [group.id for group in current_user.groups]
            document_group_ids = [group.id for group in document.groups]
            if not any(g_id in user_group_ids for g_id in document_group_ids):
                raise HTTPException(
                    status_code=403,
                    detail="Not enough permissions to access this document",
                )
        
        # Get document text - first try to read from file
        text = ""
        extraction_method = "none"
        
        if document.file_path and os.path.exists(document.file_path):
            try:
                with open(document.file_path, "rb") as f:
                    file_content = f.read()
                text = extract_text_from_file(file_content, document.filename, ["eng"])
                if text:
                    extraction_method = "file"
                    logger.info(f"Extracted text from file for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"File extraction returned empty text for document {document_id}")
            except Exception as e:
                logger.error(f"Error extracting text from file: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"Document file not found at {document.file_path}")
        
        # If file extraction failed, fall back to vector store chunks
        if not text:
            try:
                from app.services.vector_store import fetch_chunks
                docs, metas = fetch_chunks(document.file_id)
                
                if docs and len(docs) > 0:
                    # Sort chunks by index if available in metadata
                    sorted_chunks = []
                    if metas and len(metas) == len(docs):
                        # Try to sort by chunk_index if available
                        chunk_pairs = []
                        for i, doc in enumerate(docs):
                            index = metas[i].get("chunk_index", i) if metas[i] else i
                            chunk_pairs.append((index, doc))
                        
                        # Sort by index and extract just the text
                        chunk_pairs.sort(key=lambda x: x[0])
                        sorted_chunks = [pair[1] for pair in chunk_pairs]
                    else:
                        sorted_chunks = docs
                    
                    text = "\n\n".join(sorted_chunks)
                    extraction_method = "vector_store"
                    logger.info(f"Retrieved text from vector store chunks for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"No chunks found in vector store for document {document_id}")
            except Exception as e:
                logger.error(f"Error retrieving chunks from vector store: {str(e)}")
                logger.error(traceback.format_exc())
        
        if not text:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve document content from both file and vector store",
            )
        
        return {
            "document_id": document_id,
            "filename": document.filename,
            "raw_text": text,
            "text_length": len(text),
            "extraction_method": extraction_method
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error getting raw text: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error getting raw text: {str(e)}",
        )

@router.post("/documents/{document_id}/translate", response_model=dict)
async def translate_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    target_language: str,
    model: str = "phi4:latest",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Translate the document content to the specified language
    
    Args:
        document_id: The ID of the document to translate
        target_language: The target language for translation (e.g., "Spanish", "French", "German")
        model: The LLM model to use for translation
        
    Returns:
        Dictionary containing the translated text and metadata
    """
    import logging
    import traceback
    from app.services.document_processor import extract_text_from_file
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Translating document {document_id} to {target_language} using model {model}")
    
    try:
        # Get document raw text first
        raw_text_response = await get_document_raw_text(
            db=db,
            document_id=document_id,
            current_user=current_user
        )
        
        text = raw_text_response.get("raw_text", "")
        if not text:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve document content for translation",
            )
        
        # Get document details
        document = document_crud.get_document(db, id=document_id)
        
        # Prepare system prompt for translation
        system_prompt = f"""You are an expert translator. Your task is to translate the provided text from its original language to {target_language}.
        Maintain the original meaning, tone, and formatting as much as possible.
        Ensure that specialized terminology is translated accurately.
        If there are any untranslatable elements (like proper names or technical terms that should remain in the original language), keep them as is.
        """
        
        # Prepare user prompt
        user_prompt = f"""Please translate the following text to {target_language}:
        
        DOCUMENT: {document.filename}
        
        ORIGINAL TEXT:
        {text[:10000]}  # Limit text to avoid token limits
        """
        
        # Get translation from LLM with retry mechanism
        max_retries = 2
        retry_count = 0
        translated_text = ""
        
        while retry_count <= max_retries and not translated_text:
            try:
                logger.info(f"Requesting translation from LLM (attempt {retry_count + 1}/{max_retries + 1})")
                
                # Call LLM with detailed logging
                try:
                    logger.info(f"Calling llm_query with model={model}, prompt length={len(user_prompt)}, system prompt length={len(system_prompt)}")
                    translated_text = llm_query(
                        model, 
                        user_prompt,
                        system_prompt=system_prompt
                    )
                    logger.info(f"llm_query returned response type: {type(translated_text)}")
                except Exception as llm_error:
                    logger.error(f"Error in llm_query: {str(llm_error)}")
                    logger.error(traceback.format_exc())
                    raise llm_error
                
                # Validate response
                if translated_text is None:
                    logger.error("LLM returned None response")
                    translated_text = ""
                elif not isinstance(translated_text, str):
                    logger.warning(f"LLM returned non-string response: {type(translated_text)}")
                    translated_text = str(translated_text)
                
                if not translated_text or len(translated_text.strip()) < 50:
                    logger.warning(f"LLM returned empty or very short translation: '{translated_text}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                    else:
                        # If all retries failed, use a fallback message
                        logger.warning("All retries failed, using fallback message")
                        translated_text = f"Translation to {target_language} failed. Please try again later."
                else:
                    logger.info(f"Received translation from LLM, length: {len(translated_text)} chars")
            except Exception as llm_error:
                logger.error(f"Error querying LLM: {str(llm_error)}")
                logger.error(traceback.format_exc())
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                else:
                    # If all retries failed with exceptions, use a fallback message
                    logger.warning(f"Failed to generate translation after {max_retries + 1} attempts, using fallback message")
                    translated_text = f"Translation to {target_language} failed. Please try again later."
        
        return {
            "document_id": document_id,
            "filename": document.filename,
            "original_language": "auto-detected",  # We could add language detection in the future
            "target_language": target_language,
            "translated_text": translated_text,
            "model_used": model,
            "text_length": len(text),
            "translation_length": len(translated_text)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error translating document: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error translating document: {str(e)}",
        )

@router.get("/documents/{document_id}/raw-text", response_model=dict)
async def get_document_raw_text(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get the original raw text extracted from the document before chunking
    
    Args:
        document_id: The ID of the document
        
    Returns:
        Dictionary containing the raw text and metadata
    """
    import logging
    import traceback
    from app.services.document_processor import extract_text_from_file
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Getting raw text for document {document_id}")
    
    try:
        # Get document
        document = document_crud.get_document(db, id=document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )
        
        # Check permissions
        if document.owner_id != current_user.id and not document.is_public:
            # Check if document is shared with any of user's groups
            user_group_ids = [group.id for group in current_user.groups]
            document_group_ids = [group.id for group in document.groups]
            if not any(g_id in user_group_ids for g_id in document_group_ids):
                raise HTTPException(
                    status_code=403,
                    detail="Not enough permissions to access this document",
                )
        
        # Get document text - first try to read from file
        text = ""
        extraction_method = "none"
        
        if document.file_path and os.path.exists(document.file_path):
            try:
                with open(document.file_path, "rb") as f:
                    file_content = f.read()
                text = extract_text_from_file(file_content, document.filename, ["eng"])
                if text:
                    extraction_method = "file"
                    logger.info(f"Extracted text from file for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"File extraction returned empty text for document {document_id}")
            except Exception as e:
                logger.error(f"Error extracting text from file: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"Document file not found at {document.file_path}")
        
        # If file extraction failed, fall back to vector store chunks
        if not text:
            try:
                from app.services.vector_store import fetch_chunks
                docs, metas = fetch_chunks(document.file_id)
                
                if docs and len(docs) > 0:
                    # Sort chunks by index if available in metadata
                    sorted_chunks = []
                    if metas and len(metas) == len(docs):
                        # Try to sort by chunk_index if available
                        chunk_pairs = []
                        for i, doc in enumerate(docs):
                            index = metas[i].get("chunk_index", i) if metas[i] else i
                            chunk_pairs.append((index, doc))
                        
                        # Sort by index and extract just the text
                        chunk_pairs.sort(key=lambda x: x[0])
                        sorted_chunks = [pair[1] for pair in chunk_pairs]
                    else:
                        sorted_chunks = docs
                    
                    text = "\n\n".join(sorted_chunks)
                    extraction_method = "vector_store"
                    logger.info(f"Retrieved text from vector store chunks for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"No chunks found in vector store for document {document_id}")
            except Exception as e:
                logger.error(f"Error retrieving chunks from vector store: {str(e)}")
                logger.error(traceback.format_exc())
        
        if not text:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve document content from both file and vector store",
            )
        
        return {
            "document_id": document_id,
            "filename": document.filename,
            "raw_text": text,
            "text_length": len(text),
            "extraction_method": extraction_method
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error getting raw text: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error getting raw text: {str(e)}",
        )

@router.post("/documents/{document_id}/translate", response_model=dict)
async def translate_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    target_language: str,
    model: str = "phi4:latest",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Translate the document content to the specified language
    
    Args:
        document_id: The ID of the document to translate
        target_language: The target language for translation (e.g., "Spanish", "French", "German")
        model: The LLM model to use for translation
        
    Returns:
        Dictionary containing the translated text and metadata
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Translating document {document_id} to {target_language} using model {model}")
    
    try:
        # Get document raw text first
        raw_text_response = await get_document_raw_text(
            db=db,
            document_id=document_id,
            current_user=current_user
        )
        
        text = raw_text_response.get("raw_text", "")
        if not text:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve document content for translation",
            )
        
        # Get document details
        document = document_crud.get_document(db, id=document_id)
        
        # Prepare system prompt for translation
        system_prompt = f"""You are an expert translator. Your task is to translate the provided text from its original language to {target_language}.
        Maintain the original meaning, tone, and formatting as much as possible.
        Ensure that specialized terminology is translated accurately.
        If there are any untranslatable elements (like proper names or technical terms that should remain in the original language), keep them as is.
        """
        
        # Prepare user prompt
        user_prompt = f"""Please translate the following text to {target_language}:
        
        DOCUMENT: {document.filename}
        
        ORIGINAL TEXT:
        {text[:10000]}  # Limit text to avoid token limits
        """
        
        # Get translation from LLM with retry mechanism
        max_retries = 2
        retry_count = 0
        translated_text = ""
        
        while retry_count <= max_retries and not translated_text:
            try:
                logger.info(f"Requesting translation from LLM (attempt {retry_count + 1}/{max_retries + 1})")
                
                # Call LLM with detailed logging
                try:
                    logger.info(f"Calling llm_query with model={model}, prompt length={len(user_prompt)}, system prompt length={len(system_prompt)}")
                    translated_text = llm_query(
                        model, 
                        user_prompt,
                        system_prompt=system_prompt
                    )
                    logger.info(f"llm_query returned response type: {type(translated_text)}")
                except Exception as llm_error:
                    logger.error(f"Error in llm_query: {str(llm_error)}")
                    logger.error(traceback.format_exc())
                    raise llm_error
                
                # Validate response
                if translated_text is None:
                    logger.error("LLM returned None response")
                    translated_text = ""
                elif not isinstance(translated_text, str):
                    logger.warning(f"LLM returned non-string response: {type(translated_text)}")
                    translated_text = str(translated_text)
                
                if not translated_text or len(translated_text.strip()) < 50:
                    logger.warning(f"LLM returned empty or very short translation: '{translated_text}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                    else:
                        # If all retries failed, use a fallback message
                        logger.warning("All retries failed, using fallback message")
                        translated_text = f"Translation to {target_language} failed. Please try again later."
                else:
                    logger.info(f"Received translation from LLM, length: {len(translated_text)} chars")
            except Exception as llm_error:
                logger.error(f"Error querying LLM: {str(llm_error)}")
                logger.error(traceback.format_exc())
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                else:
                    # If all retries failed with exceptions, use a fallback message
                    logger.warning(f"Failed to generate translation after {max_retries + 1} attempts, using fallback message")
                    translated_text = f"Translation to {target_language} failed. Please try again later."
        
        return {
            "document_id": document_id,
            "filename": document.filename,
            "original_language": "auto-detected",  # We could add language detection in the future
            "target_language": target_language,
            "translated_text": translated_text,
            "model_used": model,
            "text_length": len(text),
            "translation_length": len(translated_text)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error translating document: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error translating document: {str(e)}",
        )

@router.get("/documents/{document_id}/analyze", response_model=dict)
async def analyze_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Analyze a document and provide insights about its content and structure
    
    Returns:
        Dictionary containing analysis results and recommended chunking strategies
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Analyzing document ID: {document_id}")
    
    # Get the document
    document = document_crud.get_document(db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if user has access to the document
    if document.owner_id != current_user.id and not document.is_public:
        # Check if user is in any of the document's groups
        user_groups = [g.id for g in current_user.groups]
        doc_groups = [g.id for g in document.groups]
        if not any(g_id in doc_groups for g_id in user_groups) and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        # Check if file exists
        text = ""
        extraction_method = "none"
        
        if document.file_path and os.path.exists(document.file_path):
            try:
                # Read the file content
                with open(document.file_path, "rb") as f:
                    file_content = f.read()
                
                # Get document text
                from app.services.document_processor import extract_text_from_file
                text = extract_text_from_file(file_content, document.filename, ["eng"])
                if text:
                    extraction_method = "file"
                    logger.info(f"Extracted text from file for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"File extraction returned empty text for document {document_id}")
            except Exception as e:
                logger.error(f"Error extracting text from file: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"Document file not found at {document.file_path}")
        
        # If file extraction failed, fall back to vector store chunks
        if not text:
            try:
                from app.services.vector_store import fetch_chunks
                docs, _ = fetch_chunks(document.file_id)
                
                if docs and len(docs) > 0:
                    text = "\n\n".join(docs)
                    extraction_method = "vector_store"
                    logger.info(f"Retrieved text from vector store chunks for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"No chunks found in vector store for document {document_id}")
            except Exception as e:
                logger.error(f"Error retrieving chunks from vector store: {str(e)}")
                logger.error(traceback.format_exc())
        
        if not text:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve document content from both file and vector store",
            )
        
        # Analyze document structure with error handling
        try:
            analysis = analyze_document_structure(text)
            logger.info(f"Document structure analysis complete for document {document_id}")
        except Exception as analysis_error:
            logger.error(f"Error analyzing document structure: {str(analysis_error)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error analyzing document structure: {str(analysis_error)}",
            )
        
        # Add document metadata
        analysis["document"] = {
            "id": document.id,
            "filename": document.filename,
            "chunk_count": document.chunk_count,
            "chunk_size": document.chunk_size,
            "chunk_overlap": document.chunk_overlap,
            "chunking_strategy": document.chunking_strategy,
            "created_at": document.created_at.isoformat(),
            "text_extraction_method": extraction_method,
            "text_length": len(text)
        }
        
        # Add recommendations with error handling
        try:
            analysis["recommendations"] = get_chunking_recommendations(analysis)
            logger.info(f"Generated chunking recommendations for document {document_id}")
        except Exception as rec_error:
            logger.error(f"Error generating chunking recommendations: {str(rec_error)}")
            logger.error(traceback.format_exc())
            analysis["recommendations"] = {
                "error": f"Failed to generate recommendations: {str(rec_error)}",
                "fallback": {
                    "chunking": {
                        "recommended_strategy": "hybrid",
                        "recommended_chunk_size": 1000,
                        "recommended_chunk_overlap": 200,
                    }
                }
            }
        
        return analysis
    
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error analyzing document: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing document: {str(e)}",
        )

@router.post("/documents/{document_id}/reprocess", response_model=Document)
async def reprocess_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    chunking_strategy: ChunkingStrategy = Form(ChunkingStrategy.HYBRID),
    ocr_languages: str = Form("eng"),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Reprocess an existing document with different chunking parameters
    
    Args:
        document_id: ID of the document to reprocess
        chunk_size: Size of text chunks in characters
        chunk_overlap: Overlap between chunks in characters
        chunking_strategy: Strategy to use for chunking
        ocr_languages: Comma-separated list of language codes for OCR
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Reprocessing document ID: {document_id}")
    
    # Get the document
    document = document_crud.get_document(db, id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if user is owner or admin
    if document.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    try:
        # Check if file exists
        if not document.file_path or not os.path.exists(document.file_path):
            raise HTTPException(status_code=404, detail="Document file not found")
        
        # Read the file content
        with open(document.file_path, "rb") as f:
            file_content = f.read()
        
        # Process document with new parameters first, before deleting existing chunks
        # This ensures we don't delete chunks if processing fails
        logger.info(f"Processing document with strategy: {chunking_strategy}")
        langs = ocr_languages.split(",")
        
        try:
            chunks, doc_metadata = process_document(
                file_content, 
                document.filename, 
                langs, 
                chunk_size, 
                chunk_overlap,
                chunking_strategy
            )
            logger.info(f"Document processing complete, got {len(chunks)} chunks")
            
            if not chunks:
                raise Exception("Document processing produced no chunks")
                
            # Now that processing succeeded, delete existing chunks
            logger.info(f"Deleting existing chunks for file ID: {document.file_id}")
            delete_file_chunks(document.file_id)
            
            # Insert new chunks into vector store
            logger.info(f"Inserting chunks into vector store")
            chunk_count = insert_chunks(chunks, document.file_id, document.filename)
            logger.info(f"Inserted {chunk_count} chunks into vector store")
            
            if chunk_count == 0:
                raise Exception("No chunks were inserted into the vector store")
                
        except Exception as proc_error:
            logger.error(f"Error during document reprocessing: {str(proc_error)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Document reprocessing failed: {str(proc_error)}")
        
        # Update document record
        logger.info(f"Updating document record in database")
        document_in = DocumentUpdate(
            chunk_count=chunk_count,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_strategy=chunking_strategy
        )
        
        updated_document = document_crud.update_document(
            db=db,
            db_obj=document,
            obj_in=document_in
        )
        
        logger.info(f"Document updated successfully with ID: {document.id}")
        return updated_document
    
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error reprocessing document: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error reprocessing document: {str(e)}",
        )

@router.delete("/documents/{document_id}", response_model=dict)
async def delete_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete a document and all related data
    
    Args:
        document_id: The ID of the document to delete
        
    Returns:
        Success message
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Deleting document {document_id}")
    
    try:
        # Get document
        document = document_crud.get_document(db, id=document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )
        
        # Check if user is the owner
        if document.owner_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions to delete this document",
            )
        
        # Store file_id for vector store deletion
        file_id = document.file_id
        
        # Track deletion status for each component
        deletion_status = {
            "file_deleted": False,
            "summaries_deleted": False,
            "chunks_deleted": False,
            "document_deleted": False
        }
        
        # First, delete chunks from vector store
        # This is important to do first as it relies on the file_id from the document
        if file_id:
            try:
                delete_file_chunks(file_id)
                logger.info(f"Deleted chunks for file_id {file_id} from vector store")
                deletion_status["chunks_deleted"] = True
            except Exception as e:
                logger.error(f"Error deleting chunks from vector store: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Delete document summaries
        try:
            from app.crud.document_summary import delete_document_summaries
            deleted_summaries = delete_document_summaries(db, document_id=document_id)
            logger.info(f"Deleted {deleted_summaries} summaries for document {document_id}")
            deletion_status["summaries_deleted"] = True
        except Exception as e:
            logger.error(f"Error deleting document summaries: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Delete document from database
        try:
            document_crud.delete_document(db, id=document_id)
            logger.info(f"Deleted document {document_id} from database")
            deletion_status["document_deleted"] = True
        except Exception as e:
            logger.error(f"Error deleting document from database: {str(e)}")
            logger.error(traceback.format_exc())
            # If we can't delete from database, still try to delete the file
        
        # Delete file from disk (do this last)
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
                logger.info(f"Deleted file from disk: {document.file_path}")
                deletion_status["file_deleted"] = True
            except Exception as e:
                logger.error(f"Error deleting file from disk: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Check if any deletion failed
        if not all(deletion_status.values()):
            logger.warning(f"Partial document deletion: {deletion_status}")
            # Continue anyway as we've done our best to clean up
        
        return {
            "success": True,
            "message": f"Document {document_id} and all related data successfully deleted"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error deleting document: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting document: {str(e)}",
        )

@router.post("/documents/{document_id}/summarize", response_model=DocumentSummary)
async def summarize_document(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    model: str = "phi4:latest",
    summary_type: str = "comprehensive",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Generate a summary for a document
    
    Args:
        document_id: The ID of the document to summarize
        model: The LLM model to use for summarization
        summary_type: Type of summary to generate (comprehensive, concise, key_points)
        
    Returns:
        The created document summary
    """
    import logging
    import traceback
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Generating {summary_type} summary for document {document_id} using model {model}")
    
    try:
        # Get document
        document = document_crud.get_document(db, id=document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )
        
        # Check if user has access to this document
        if document.owner_id != current_user.id and not document.is_public:
            # Check if document is shared with any of user's groups
            user_group_ids = [group.id for group in current_user.groups]
            document_group_ids = [group.id for group in document.groups]
            if not any(g_id in user_group_ids for g_id in document_group_ids):
                raise HTTPException(
                    status_code=403,
                    detail="Not enough permissions to access this document",
                )
        
        # Get document text - first try to read from file
        text = ""
        extraction_method = "none"
        
        if document.file_path and os.path.exists(document.file_path):
            try:
                with open(document.file_path, "rb") as f:
                    file_content = f.read()
                text = extract_text_from_file(file_content, document.filename, ["eng"])
                if text:
                    extraction_method = "file"
                    logger.info(f"Extracted text from file for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"File extraction returned empty text for document {document_id}")
            except Exception as e:
                logger.error(f"Error extracting text from file: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"Document file not found at {document.file_path}")
        
        # If file extraction failed, fall back to vector store chunks
        if not text:
            try:
                from app.services.vector_store import fetch_chunks
                docs, metas = fetch_chunks(document.file_id)
                
                if docs and len(docs) > 0:
                    # Sort chunks by index if available in metadata
                    sorted_chunks = []
                    if metas and len(metas) == len(docs):
                        # Try to sort by chunk_index if available
                        chunk_pairs = []
                        for i, doc in enumerate(docs):
                            index = metas[i].get("chunk_index", i) if metas[i] else i
                            chunk_pairs.append((index, doc))
                        
                        # Sort by index and extract just the text
                        chunk_pairs.sort(key=lambda x: x[0])
                        sorted_chunks = [pair[1] for pair in chunk_pairs]
                    else:
                        sorted_chunks = docs
                    
                    text = "\n\n".join(sorted_chunks)
                    extraction_method = "vector_store"
                    logger.info(f"Retrieved text from vector store chunks for document {document_id}, length: {len(text)} chars")
                else:
                    logger.warning(f"No chunks found in vector store for document {document_id}")
            except Exception as e:
                logger.error(f"Error retrieving chunks from vector store: {str(e)}")
                logger.error(traceback.format_exc())
        
        if not text:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve document content from both file and vector store",
            )
        
        # Generate system prompt and user prompt based on summary type
        system_prompt = ""
        user_prompt = ""
        
        if summary_type == "comprehensive":
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries.

Your task is to create a detailed summary that:
1. Captures all major points, key arguments, and important details from the document
2. Organizes content in a clear, logical structure with proper markdown formatting
3. Uses headings (## for main sections, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Ends with a concise conclusion that synthesizes the main takeaways
7. Maintains the document's original flow and organization
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the original, highlighting the most valuable information."""
            
            user_prompt = f"""Please provide a comprehensive summary of the following document using proper markdown formatting:
            
            DOCUMENT: {document.filename}
            
            CONTENT:
            {text[:10000]}"""
            
        elif summary_type == "concise":
            system_prompt = """You are an expert document summarizer specializing in creating concise, impactful summaries with excellent markdown formatting.

Your task is to create a brief summary that:
1. Focuses only on the most essential information and key points
2. Uses clear, direct language with no unnecessary words
3. Organizes content with simple markdown formatting
4. Includes a very brief introduction and conclusion
5. Uses bullet points for key items where appropriate
6. Emphasizes the most important concepts using **bold** formatting
7. Keeps the summary to approximately 20-25% the length of the original
8. Maintains perfect clarity while being extremely brief

Your summary should capture the essence of the document in the most efficient way possible."""
            
            user_prompt = f"""Please provide a concise summary of the following document using clean markdown formatting:
            
            DOCUMENT: {document.filename}
            
            CONTENT:
            {text[:10000]}"""
            
        elif summary_type == "key_points":
            system_prompt = """You are an expert document analyzer specializing in extracting and organizing key points with perfect markdown formatting.

Your task is to create a structured list of key points that:
1. Identifies and extracts the most important information from the document
2. Organizes points in a logical, hierarchical structure using markdown
3. Uses bullet points (- ) for main items and sub-bullets for supporting details
4. Groups related points under clear ## headings
5. Focuses on actionable insights and main takeaways
6. Highlights critical information with **bold** formatting
7. Keeps each point direct, clear and concise
8. Includes a brief 1-2 sentence introduction and conclusion

Your key points should provide a reader with all essential information in an easily scannable format."""
            
            user_prompt = f"""Please extract and organize the key points from the following document using proper markdown formatting:
            
            DOCUMENT: {document.filename}
            
            CONTENT:
            {text[:10000]}"""
            
        else:
            # Default to comprehensive
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries.

Your task is to create a detailed summary that:
1. Captures all major points, key arguments, and important details from the document
2. Organizes content in a clear, logical structure with proper markdown formatting
3. Uses headings (## for main sections, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Ends with a concise conclusion that synthesizes the main takeaways
7. Maintains the document's original flow and organization
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the original, highlighting the most valuable information."""
            
            user_prompt = f"""Please provide a comprehensive summary of the following document using proper markdown formatting:
            
            DOCUMENT: {document.filename}
            
            CONTENT:
            {text[:10000]}"""
        
        # Get summary from LLM with retry mechanism
        max_retries = 2
        retry_count = 0
        summary_text = ""
        
        while retry_count <= max_retries and not summary_text:
            try:
                logger.info(f"Requesting summary from LLM (attempt {retry_count + 1}/{max_retries + 1})")
                
                # Call LLM with detailed logging
                try:
                    logger.info(f"Calling llm_query with model={model}, prompt length={len(user_prompt)}, system prompt length={len(system_prompt)}")
                    # Set max_tokens based on summary type
                    max_tokens = 2000  # Default
                    if summary_type == "comprehensive":
                        max_tokens = 3000
                    elif summary_type == "concise":
                        max_tokens = 1000
                    elif summary_type == "key_points":
                        max_tokens = 1500
                        
                    summary_text = llm_query(
                        model, 
                        user_prompt,
                        max_tokens=max_tokens,
                        system_prompt=system_prompt
                    )
                    logger.info(f"llm_query returned response type: {type(summary_text)}")
                except Exception as llm_error:
                    logger.error(f"Error in llm_query: {str(llm_error)}")
                    logger.error(traceback.format_exc())
                    raise llm_error
                
                # Validate response
                if summary_text is None:
                    logger.error("LLM returned None response")
                    summary_text = ""
                elif not isinstance(summary_text, str):
                    logger.warning(f"LLM returned non-string response: {type(summary_text)}")
                    summary_text = str(summary_text)
                
                if not summary_text or len(summary_text.strip()) < 50:
                    logger.warning(f"LLM returned empty or very short summary: '{summary_text}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                    else:
                        # If all retries failed, use a fallback summary
                        logger.warning("All retries failed, using fallback summary")
                        summary_text = generate_fallback_summary(document.filename, summary_type)
                else:
                    logger.info(f"Received summary from LLM, length: {len(summary_text)} chars")
            except Exception as llm_error:
                logger.error(f"Error querying LLM: {str(llm_error)}")
                logger.error(traceback.format_exc())
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                else:
                    # If all retries failed with exceptions, use a fallback summary
                    logger.warning(f"Failed to generate summary after {max_retries + 1} attempts, using fallback summary")
                    summary_text = generate_fallback_summary(document.filename, summary_type)
        
        # Create summary record with summary type and extraction method
        summary_in = DocumentSummaryCreate(
            document_id=document_id,
            summary_text=summary_text,
            model_used=model,
            summary_type=summary_type,
            metadata={
                "text_extraction_method": extraction_method,
                "text_length": len(text),
                "prompt_length": len(user_prompt),
                "system_prompt_length": len(system_prompt),
                "max_tokens": max_tokens,
                "summary_length": len(summary_text)
            }
        )
        
        summary = document_crud.create_document_summary(db=db, obj_in=summary_in)
        logger.info(f"Created {summary_type} summary for document {document_id}, length: {len(summary_text)} chars")
        
        return summary
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error generating summary: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error generating summary: {str(e)}",
        )

@router.post("/documents/bulk-summarize", response_model=dict)
async def bulk_summarize_documents(
    *,
    db: Session = Depends(get_db),
    document_ids: List[int],
    summary_type: str = "comprehensive",
    model: str = "phi4:latest",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Generate a summary for multiple documents
    
    Args:
        document_ids: List of document IDs to summarize
        summary_type: Type of summary to generate (comprehensive, concise, key_points)
        model: The LLM model to use for summarization
        
    Returns:
        Dictionary with the combined summary
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Generating {summary_type} bulk summary for {len(document_ids)} documents using model {model}")
    
    try:
        # Get documents and check permissions
        documents = []
        for doc_id in document_ids:
            document = document_crud.get_document(db, id=doc_id)
            if not document:
                continue
                
            # Check if user has access to this document
            if document.owner_id != current_user.id and not document.is_public:
                # Check if document is shared with any of user's groups
                user_group_ids = [group.id for group in current_user.groups]
                document_group_ids = [group.id for group in document.groups]
                if not any(g_id in user_group_ids for g_id in document_group_ids):
                    continue
            
            documents.append(document)
        
        if not documents:
            raise HTTPException(
                status_code=404,
                detail="No accessible documents found with the provided IDs",
            )
        
        # Extract text from all documents
        document_texts = []
        for document in documents:
            text = ""
            
            # Try to read from file
            if document.file_path and os.path.exists(document.file_path):
                try:
                    with open(document.file_path, "rb") as f:
                        file_content = f.read()
                    text = extract_text_from_file(file_content, document.filename, ["eng"])
                except Exception as e:
                    logger.error(f"Error extracting text from file: {str(e)}")
            
            # If file extraction failed, fall back to vector store chunks
            if not text:
                try:
                    from app.services.vector_store import fetch_chunks
                    docs, metas = fetch_chunks(document.file_id)
                    
                    if docs and len(docs) > 0:
                        # Sort chunks by index if available in metadata
                        sorted_chunks = []
                        if metas and len(metas) == len(docs):
                            # Try to sort by chunk_index if available
                            chunk_pairs = []
                            for i, doc in enumerate(docs):
                                index = metas[i].get("chunk_index", i) if metas[i] else i
                                chunk_pairs.append((index, doc))
                            
                            # Sort by index and extract just the text
                            chunk_pairs.sort(key=lambda x: x[0])
                            sorted_chunks = [pair[1] for pair in chunk_pairs]
                        else:
                            sorted_chunks = docs
                        
                        text = "\n\n".join(sorted_chunks)
                except Exception as e:
                    logger.error(f"Error retrieving chunks from vector store: {str(e)}")
            
            if text:
                document_texts.append({
                    "id": document.id,
                    "filename": document.filename,
                    "text": text[:5000]  # Limit text to avoid token limits
                })
        
        if not document_texts:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve content from any of the selected documents",
            )
        
        # Generate system prompt based on summary type
        system_prompt = ""
        if summary_type == "comprehensive":
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries of multiple documents a detailed summary that:
1. Captures all major points, key arguments, and important details from each document
2. Organizes content in a clear, logical, logical structure with proper markdown formatting
3. Uses headings (## for document names, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Identifies connections and relationships between documents
7. Ends withing concise conclusion that synthesizes the main takeaways
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the originals, highlighting the most valuable information."""
        elif summary_type == "concise":
            system_prompt = """You are an expert document summarizer specializing in creating concise, impactful, impactful summarieies of multiple documents with excellent markdown formatting.

Your task is to create a brief summary that:
1. Focuses only on the most essential information and key points from each document
2. Uses clear, direct language with no unnecessary words
3. Organizes content with simple markdown formatting and clear document sections
4. Includes a very brief introduction and conclusion
5. Uses bullet points for key items where appropriate
6. Emphasizes the most important concepts using **bold** formatting
7. Keeps the summary brief and efficient
8. Maintains perfect clarity while being extremely concise

Your summary should capture the essence of all documents in the most efficient way possible."""
        elif summary_type == "key_points":
            system_prompt = """You are an expert document analyzer specializing in extracting and organizing key points from multiple documents with perfect markdown formatting.

Your task is to create a structured list of key points that:
1. Identifies and extracts the most important information from each document
2. Organizes points in a logical structure using markdown with clear document sections
3. Uses bullet points (- ) for main items and sub-bullets for supporting details
4. Groups related points under clear ## headings for each document
5. Focuses on actionable insights and main takeaways
6. Highlights critical information with **bold** formatting
7. Keeps each point direct, clear and concise
8. Includes a brief 1-2 sentence introduction and conclusion

Your key points should provide a reader with all essential information in an easily scannable format."""
        else:
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries of multiple documents.

Your task is to create a detailed summary that:
1. Captures all major points, key arguments, and important details from each document
2. Organizes content in a clear, logical structure with proper markdown formatting
3. Uses headings (## for document names, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Identifies connections and relationships between documents
7. Ends with a concise conclusion that synthesizes the main takeaways
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the originals, highlighting the most valuable information."""
        
        # Prepare user prompt with document contents
        user_prompt = f"""Please provide a {summary_type} summary of the following {len(document_texts)} documents using proper markdown formatting:

"""
        
        for i, doc in enumerate(document_texts):
            user_prompt += f"DOCUMENT {i+1}: {doc['filename']}\n\n"
            user_prompt += f"{doc['text']}\n\n"
            user_prompt += "---\n\n"
        
        # Get summary from LLM with retry mechanism
        max_retries = 2
        retry_count = 0
        summary_text = ""
        
        while retry_count <= max_retries and not summary_text:
            try:
                logger.info(f"Requesting bulk summary from LLM (attempt {retry_count + 1}/{max_retries + 1})")
                
                # Use system prompt with the LLM query
                summary_text = llm_query(
                    model, 
                    user_prompt,
                    system_prompt=system_prompt
                )
                
                if not summary_text or len(summary_text.strip()) < 50:
                    logger.warning(f"LLM returned empty or very short summary: '{summary_text}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                    else:
                        raise Exception("LLM returned empty or very short summary after multiple attempts")
                else:
                    logger.info(f"Received bulk summary from LLM, length: {len(summary_text)} chars")
            except Exception as llm_error:
                logger.error(f"Error querying LLM: {str(llm_error)}")
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                else:
                    raise Exception(f"Failed to generate summary after {max_retries + 1} attempts: {str(llm_error)}")
        
        return {
            "summary": summary_text,
            "summary_type": summary_type,
            "document_count": len(document_texts),
            "documents": [{"id": doc["id"], "filename": doc["filename"]} for doc in document_texts]
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error generating bulk summary: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error generating bulk summary: {str(e)}",
        )

@router.post("/summarize/text", response_model=dict)
async def summarize_text(
    *,
    text: str,
    summary_type: str = "comprehensive",
    model: str = "phi4:latest",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Generate a summary for arbitrary text input
    
    Args:
        text: The text to summarize
        summary_type: Type of summary to generate (comprehensive, concise, key_points)
        model: The LLM model to use for summarization
        
    Returns:
        Dictionary with the summary
    """
    import logging
    import traceback
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Generating {summary_type} summary for text input using model {model}")
    
    try:
        if not text or len(text.strip()) < 100:
            raise HTTPException(
                status_code=400,
                detail="Text input is too short. Please provide more content to summarize.",
            )
        
        # Generate system prompt based on summary type
        system_prompt = ""
        if summary_type == "comprehensive":
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries.

Your task is to create a detailed summary that:
1. Captures all major points, key arguments, and important details from the document
2. Organizes content in a clear, logical structure with proper markdown formatting
3. Uses headings (## for main sections, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Ends with a concise conclusion that synthesizes the main takeaways
7. Maintains the document's original flow and organization
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the original, highlighting the most valuable information."""
        elif summary_type == "concise":
            system_prompt = """You are an expert document summarizer specializing in creating concise, impactful summaries with excellent markdown formatting.

Your task is to create a brief summary that:
1. Focuses only on the most essential information and key points
2. Uses clear, direct language with no unnecessary words
3. Organizes content with simple markdown formatting
4. Includes a very brief introduction and conclusion
5. Uses bullet points for key items where appropriate
6. Emphasizes the most important concepts using **bold** formatting
7. Keeps the summary to approximately 20-25% the length of the original
8. Maintains perfect clarity while being extremely brief

Your summary should capture the essence of the document in the most efficient way possible."""
        elif summary_type == "key_points":
            system_prompt = """You are an expert document analyzer specializing in extracting and organizing key points with perfect markdown formatting.

Your task is to create a structured list of key points that:
1. Identifies and extracts the most important information from the document
2. Organizes points in a logical, hierarchical structure using markdown
3. Uses bullet points (- ) for main items and sub-bullets for supporting details
4. Groups related points under clear ## headings
5. Focuses on actionable insights and main takeaways
6. Highlights critical information with **bold** formatting
7. Keeps each point direct, clear and concise
8. Includes a brief 1-2 sentence introduction and conclusion

Your key points should provide a reader with all essential information in an easily scannable format."""
        else:
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries.

Your task is to create a detailed summary that:
1. Captures all major points, key arguments, and important details from the document
2. Organizes content in a clear, logical structure with proper markdown formatting
3. Uses headings (## for main sections, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Ends with a concise conclusion that synthesizes the main takeaways
7. Maintains the document's original flow and organization
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the original, highlighting the most valuable information."""
        
        # Prepare user prompt
        user_prompt = f"""Please provide a {summary_type} summary of the following text using proper markdown formatting:

CONTENT:
{text[:10000]}"""  # Limit text to avoid token limits
        
        # Set max_tokens based on summary type
        max_tokens = 2000  # Default
        if summary_type == "comprehensive":
            max_tokens = 3000
        elif summary_type == "concise":
            max_tokens = 1000
        elif summary_type == "key_points":
            max_tokens = 1500
        
        # Get summary from LLM with retry mechanism
        max_retries = 2
        retry_count = 0
        summary_text = ""
        
        while retry_count <= max_retries and not summary_text:
            try:
                logger.info(f"Requesting text summary from LLM (attempt {retry_count + 1}/{max_retries + 1})")
                
                # Use system prompt with the LLM query and max_tokens
                summary_text = llm_query(
                    model, 
                    user_prompt,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt
                )
                
                if not summary_text or len(summary_text.strip()) < 50:
                    logger.warning(f"LLM returned empty or very short summary: '{summary_text}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                    else:
                        raise Exception("LLM returned empty or very short summary after multiple attempts")
                else:
                    logger.info(f"Received text summary from LLM, length: {len(summary_text)} chars")
            except Exception as llm_error:
                logger.error(f"Error querying LLM: {str(llm_error)}")
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                else:
                    raise Exception(f"Failed to generate summary after {max_retries + 1} attempts: {str(llm_error)}")
        
        return {
            "summary": summary_text,
            "summary_type": summary_type,
            "text_length": len(text)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing text: {str(e)}")
        logger.error(traceback.format_exc())
        
        raise HTTPException(
            status_code=500,
            detail=f"Error summarizing text: {str(e)}",
        )

@router.post("/summarize/url", response_model=dict)
async def summarize_url(
    *,
    url: str,
    summary_type: str = "comprehensive",
    model: str = "phi4:latest",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Generate a summary for content from a URL
    
    Args:
        url: The URL to fetch and summarize
        summary_type: Type of summary to generate (comprehensive, concise, key_points)
        model: The LLM model to use for summarization
        
    Returns:
        Dictionary with the summary
    """
    import logging
    import traceback
    import requests
    from bs4 import BeautifulSoup
    
    logger = logging.getLogger("uvicorn")
    logger.info(f"Generating {summary_type} summary for URL: {url} using model {model}")
    
    try:
        # Validate URL
        if not url or not url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=400,
                detail="Invalid URL. Please provide a valid URL starting with http:// or https://",
            )
        
        # Fetch URL content
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Error fetching URL: {str(req_err)}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch content from URL: {str(req_err)}",
            )
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        
        # Get text
        text = soup.get_text()
        
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        if not text or len(text.strip()) < 100:
            raise HTTPException(
                status_code=400,
                detail="Extracted text is too short. Please provide a URL with more content to summarize.",
            )
        
        # Generate system prompt based on summary type
        system_prompt = ""
        if summary_type == "comprehensive":
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries.

Your task is to create a detailed summary that:
1. Captures all major points, key arguments, and important details from the document
2. Organizes content in a clear, logical structure with proper markdown formatting
3. Uses headings (## for main sections, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Ends with a concise conclusion that synthesizes the main takeaways
7. Maintains the document's original flow and organization
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the original, highlighting the most valuable information."""
        elif summary_type == "concise":
            system_prompt = """You are an expert document summarizer specializing in creating concise, impactful summaries with excellent markdown formatting.

Your task is to create a brief summary that:
1. Focuses only on the most essential information and key points
2. Uses clear, direct language with no unnecessary words
3. Organizes content with simple markdown formatting
4. Includes a very brief introduction and conclusion
5. Uses bullet points for key items where appropriate
6. Emphasizes the most important concepts using **bold** formatting
7. Keeps the summary to approximately 20-25% the length of the original
8. Maintains perfect clarity while being extremely brief

Your summary should capture the essence of the document in the most efficient way possible."""
        elif summary_type == "key_points":
            system_prompt = """You are an expert document analyzer specializing in extracting and organizing key points with perfect markdown formatting.

Your task is to create a structured list of key points that:
1. Identifies and extracts the most important information from the document
2. Organizes points in a logical, hierarchical structure using markdown
3. Uses bullet points (- ) for main items and sub-bullets for supporting details
4. Groups related points under clear ## headings
5. Focuses on actionable insights and main takeaways
6. Highlights critical information with **bold** formatting
7. Keeps each point direct, clear and concise
8. Includes a brief 1-2 sentence introduction and conclusion

Your key points should provide a reader with all essential information in an easily scannable format."""
        else:
            system_prompt = """You are an expert document summarizer with exceptional skills in creating well-structured, comprehensive summaries.

Your task is to create a detailed summary that:
1. Captures all major points, key arguments, and important details from the document
2. Organizes content in a clear, logical structure with proper markdown formatting
3. Uses headings (## for main sections, ### for subsections) to organize content
4. Includes bullet points or numbered lists where appropriate
5. Provides a brief introduction at the beginning
6. Ends with a concise conclusion that synthesizes the main takeaways
7. Maintains the document's original flow and organization
8. Uses proper markdown formatting for emphasis, lists, and sections

Your summary should be thorough yet more concise than the original, highlighting the most valuable information."""
        
        # Prepare user prompt
        user_prompt = f"""Please provide a {summary_type} summary of the content from this URL using proper markdown formatting:

URL: {url}

CONTENT:
{text[:10000]}"""  # Limit text to avoid token limits
        
        # Set max_tokens based on summary type
        max_tokens = 2000  # Default
        if summary_type == "comprehensive":
            max_tokens = 3000
        elif summary_type == "concise":
            max_tokens = 1000
        elif summary_type == "key_points":
            max_tokens = 1500
        
        # Get summary from LLM with retry mechanism
        max_retries = 2
        retry_count = 0
        summary_text = ""
        
        while retry_count <= max_retries and not summary_text:
            try:
                logger.info(f"Requesting URL summary from LLM (attempt {retry_count + 1}/{max_retries + 1})")
                
                # Use system prompt with the LLM query
                summary_text = llm_query(
                    model, 
                    user_prompt,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt
                )
                
                if not summary_text or len(summary_text.strip()) < 50:
                    logger.warning(f"LLM returned empty or very short summary: '{summary_text}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                    else:
                        raise Exception("LLM returned empty or very short summary after multiple attempts")
                else:
                    logger.info(f"Received URL summary from LLM, length: {len(summary_text)} chars")
            except Exception as llm_error:
                logger.error(f"Error querying LLM: {str(llm_error)}")
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                else:
                    raise Exception(f"Failed to generate summary after {max_retries + 1} attempts: {str(llm_error)}")
        
        return {
            "summary": summary_text,
            "summary_type": summary_type,
            "url": url,
            "text_length": len(text)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error generating text summary: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error generating text summary: {str(e)}",
        )

@router.post("/summarize/url", response_model=dict)
async def summarize_url(
    *,
    url: str,
    summary_type: str = "comprehensive",
    model: str = "phi4:latest",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Generate a summary for web content from a URL
    
    Args:
        url: The URL to fetch and summarize
        summary_type: Type of summary to generate (comprehensive, concise, key_points)
        model: The LLM model to use for summarization
        
    Returns:
        Dictionary with the summary
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Generating {summary_type} summary for URL: {url} using model {model}")
    
    try:
        # Validate URL
        if not url or not url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=400,
                detail="Invalid URL. Please provide a valid URL starting with http:// or https://",
            )
        
        # Fetch URL content
        import requests
        from bs4 import BeautifulSoup
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML and extract text
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()
            
            # Get text
            text = soup.get_text(separator='\n')
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            if not text or len(text.strip()) < 100:
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract sufficient text content from the provided URL.",
                )
                
            logger.info(f"Successfully extracted {len(text)} characters from URL")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Error fetching URL content: {str(e)}",
            )
        
        # Generate system prompt based on summary type
        system_prompt = ""
        if summary_type == "comprehensive":
            system_prompt = """You are an expert web content summarizer. Your task is to create a comprehensive summary of the provided web content.
            Include all major points, key arguments, and important details.
            Organize the summary in a clear structure that follows the original content's organization.
            Ensure the summary is thorough while still being more concise than the original."""
        elif summary_type == "concise":
            system_prompt = """You are an expert web content summarizer. Your task is to create a concise summary of the provided web content.
            Focus only on the most important information and keep it brief.
            Aim for a summary that is about 20-25% the length of the original content.
            Prioritize clarity and brevity while capturing the essential meaning."""
        elif summary_type == "key_points":
            system_prompt = """You are an expert web content summarizer. Your task is to extract key points from the provided web content.
            Present the information as a bullet-point list.
            Focus on the main takeaways and actionable insights.
            Be direct and concise with each point."""
        else:
            system_prompt = """You are an expert web content summarizer. Your task is to summarize the provided web content.
            Provide a balanced summary that captures the essential information."""
        
        # Prepare user prompt
        user_prompt = f"Please summarize the following web content from {url}:\n\n{text[:10000]}"  # Limit text to avoid token limits
        
        # Get summary from LLM with retry mechanism
        max_retries = 2
        retry_count = 0
        summary_text = ""
        
        while retry_count <= max_retries and not summary_text:
            try:
                logger.info(f"Requesting URL summary from LLM (attempt {retry_count + 1}/{max_retries + 1})")
                
                # Use system prompt with the LLM query
                summary_text = llm_query(
                    model, 
                    user_prompt,
                    system_prompt=system_prompt
                )
                
                if not summary_text or len(summary_text.strip()) < 50:
                    logger.warning(f"LLM returned empty or very short summary: '{summary_text}'")
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                    else:
                        raise Exception("LLM returned empty or very short summary after multiple attempts")
                else:
                    logger.info(f"Received URL summary from LLM, length: {len(summary_text)} chars")
            except Exception as llm_error:
                logger.error(f"Error querying LLM: {str(llm_error)}")
                if retry_count < max_retries:
                    retry_count += 1
                    logger.info(f"Retrying LLM query (attempt {retry_count + 1}/{max_retries + 1})")
                else:
                    raise Exception(f"Failed to generate summary after {max_retries + 1} attempts: {str(llm_error)}")
        
        return {
            "summary": summary_text,
            "summary_type": summary_type,
            "url": url,
            "title": soup.title.string if soup.title else url,
            "content_length": len(text)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error with traceback
        import traceback
        logger.error(f"Error generating URL summary: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Error generating URL summary: {str(e)}",
        )

@router.get("/documents/{document_id}/summaries/{summary_id}/export", response_class=Response)
def export_document_summary(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    summary_id: int,
    format: str = "docx",
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Export a document summary to different formats
    Currently supported: docx
    """
    document = document_crud.get_document(db, id=document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )
    
    # Check if user has access to this document
    if document.owner_id != current_user.id and not document.is_public:
        # Check if document is shared with any of user's groups
        user_group_ids = [group.id for group in current_user.groups]
        document_group_ids = [group.id for group in document.groups]
        if not any(g_id in user_group_ids for g_id in document_group_ids):
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions to access this document",
            )
    
    # Get the summary
    summary = document_crud.get_document_summary(db, id=summary_id)
    if not summary or summary.document_id != document_id:
        raise HTTPException(
            status_code=404,
            detail="Summary not found",
        )
    
    if format.lower() == "docx":
        # Export to DOCX
        docx_bytes = export_to_docx(
            summary_text=summary.summary_text,
            filename=document.filename,
            model_used=summary.model_used,
            created_at=summary.created_at
        )
        
        # Return as downloadable file
        filename = f"{document.filename.split('.')[0]}_summary.docx"
        return StreamingResponse(
            iter([docx_bytes]),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format: {format}"
        )

@router.get("/documents/{document_id}/summaries", response_model=List[DocumentSummary])
def get_document_summaries(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get all summaries for a document
    """
    document = document_crud.get_document(db, id=document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )
    
    # Check if user has access to this document
    if document.owner_id != current_user.id and not document.is_public:
        # Check if document is shared with any of user's groups
        user_group_ids = [group.id for group in current_user.groups]
        document_group_ids = [group.id for group in document.groups]
        if not any(g_id in user_group_ids for g_id in document_group_ids):
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions to access this document",
            )
    
    summaries = document_crud.get_document_summaries(db=db, document_id=document_id)
    
    return summaries

from fastapi import Request

@router.get("/some-endpoint")
async def get_doc(request: Request):
    document_id = request.query_params.get("document_id")
    ...
