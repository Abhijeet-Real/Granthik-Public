"""
Enhanced document processing service for GRANTHIK
"""
import os
import re
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime

from app.core.config import settings
from app.services.ocr import ocr_parse

logger = logging.getLogger("uvicorn")

class ChunkingStrategy(str, Enum):
    """Enum for different chunking strategies"""
    FIXED_SIZE = "fixed_size"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    HYBRID = "hybrid"
    
def extract_text_from_file(file_content: bytes, filename: str, langs: List[str]) -> str:
    """
    Extract text from a file using OCR
    
    Args:
        file_content: The binary content of the file
        filename: The name of the file
        langs: List of language codes for OCR
        
    Returns:
        Extracted text as a string
    """
    logger.info(f"Extracting text from file: {filename}")
    
    try:
        # Get raw elements from Unstructured API
        r = requests.post(
            settings.UNSTRUCTURED_URL,
            files={"files": (filename, file_content)},
            data={"ocr_languages": ",".join(langs)}
        )
        r.raise_for_status()
        elements = r.json()
        
        # Extract all text from elements
        all_text = ""
        for element in elements:
            if "text" in element and element["text"]:
                all_text += element["text"] + "\n\n"
        
        logger.info(f"Extracted {len(all_text)} characters of text from {filename}")
        return all_text
        
    except Exception as e:
        # Log the error
        logger.error(f"Text extraction error: {str(e)}")
        raise Exception(f"Failed to extract text from document: {str(e)}")

def extract_metadata(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Extract metadata from a document
    
    Args:
        file_content: The binary content of the file
        filename: The name of the file
        
    Returns:
        Dictionary of metadata
    """
    metadata = {
        "filename": filename,
        "file_size": len(file_content),
        "extraction_date": datetime.utcnow().isoformat(),
    }
    
    # Extract file extension
    _, ext = os.path.splitext(filename)
    metadata["file_type"] = ext.lower().lstrip(".")
    
    # Add more metadata extraction based on file type
    # For example, extract PDF metadata, image dimensions, etc.
    
    return metadata

def process_document(
    file_content: bytes, 
    filename: str, 
    langs: List[str] = ["eng"], 
    chunk_size: int = 1000, 
    chunk_overlap: int = 200,
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.HYBRID
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Process a document with enhanced chunking and metadata extraction
    
    Args:
        file_content: The binary content of the file
        filename: The name of the file
        langs: List of language codes for OCR
        chunk_size: Size of text chunks in characters
        chunk_overlap: Overlap between chunks in characters
        chunking_strategy: Strategy to use for chunking
        
    Returns:
        Tuple of (chunks, metadata)
    """
    import gc
    
    logger.info(f"Processing document: {filename}")
    logger.info(f"Chunking strategy: {chunking_strategy}, size: {chunk_size}, overlap: {chunk_overlap}")
    
    # Extract metadata
    metadata = extract_metadata(file_content, filename)
    logger.info(f"Extracted metadata: {metadata}")
    
    try:
        # Get raw text from document using OCR service with memory-efficient approach
        logger.info(f"Starting OCR processing with memory-efficient approach")
        raw_chunks = ocr_parse(file_content, filename, langs)
        
        # Extract text in a memory-efficient way
        logger.info(f"Extracting text from OCR results")
        all_text = ""
        for element in raw_chunks:
            if "text" in element and element["text"]:
                all_text += element["text"] + "\n\n"
        
        # Free up memory
        del raw_chunks
        gc.collect()
        
        logger.info(f"Extracted {len(all_text)} characters of text")
        
        # Apply chunking strategy with memory efficiency in mind
        logger.info(f"Applying chunking strategy: {chunking_strategy}")
        
        # For very large texts, use paragraph chunking regardless of specified strategy
        if len(all_text) > 1000000:  # 1MB of text
            logger.info(f"Text is very large ({len(all_text)} chars), forcing paragraph chunking")
            chunks = chunk_text_by_paragraph(all_text, filename, metadata)
        else:
            if chunking_strategy == ChunkingStrategy.FIXED_SIZE:
                chunks = chunk_text_fixed_size(all_text, chunk_size, chunk_overlap, filename, metadata)
            elif chunking_strategy == ChunkingStrategy.PARAGRAPH:
                chunks = chunk_text_by_paragraph(all_text, filename, metadata)
            elif chunking_strategy == ChunkingStrategy.SENTENCE:
                chunks = chunk_text_by_sentence(all_text, chunk_size, chunk_overlap, filename, metadata)
            else:  # Default to hybrid
                chunks = chunk_text_hybrid(all_text, chunk_size, chunk_overlap, filename, metadata)
        
        # Free up memory
        del all_text
        gc.collect()
        
        logger.info(f"Created {len(chunks)} chunks using {chunking_strategy} strategy")
        
        return chunks, metadata
        
    except Exception as e:
        logger.error(f"Error in document processing: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def chunk_text_fixed_size(
    text: str, 
    chunk_size: int, 
    chunk_overlap: int, 
    filename: str,
    metadata: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Chunk text into fixed-size chunks with overlap
    
    Args:
        text: The text to chunk
        chunk_size: Size of text chunks in characters
        chunk_overlap: Overlap between chunks in characters
        filename: The name of the file
        metadata: Document metadata
        
    Returns:
        List of text chunks
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    # Validate inputs
    if chunk_size <= 0:
        logger.warning(f"Invalid chunk_size: {chunk_size}, using default of 1000")
        chunk_size = 1000
    
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        logger.warning(f"Invalid chunk_overlap: {chunk_overlap}, using default of 200")
        chunk_overlap = min(200, chunk_size // 5)
    
    # Sanitize text to avoid encoding issues
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Check if text is too large (over 10MB) and log warning
    if len(text) > 10 * 1024 * 1024:
        logger.warning(f"Very large text to chunk: {len(text) / 1024 / 1024:.2f} MB")
    
    chunks = []
    start = 0
    max_iterations = len(text) * 2  # Safety limit for iterations
    iteration_count = 0
    
    while start < len(text) and iteration_count < max_iterations:
        iteration_count += 1
        
        # Get chunk of text
        end = min(start + chunk_size, len(text))
        
        # If not at the end, try to find a good break point
        if end < len(text):
            # Look for paragraph break (with reasonable limit on search)
            max_search_len = min(end - start, 10000)  # Limit regex search to avoid performance issues
            search_end = end
            search_start = max(start, end - max_search_len)
            
            paragraph_break = text.rfind("\n\n", search_start, search_end)
            if paragraph_break != -1 and paragraph_break > start + chunk_size // 2:
                end = paragraph_break + 2  # Include the newlines
            else:
                # Look for sentence break
                sentence_break = max(
                    text.rfind(". ", search_start, search_end),
                    text.rfind("! ", search_start, search_end),
                    text.rfind("? ", search_start, search_end)
                )
                if sentence_break != -1 and sentence_break > start + chunk_size // 2:
                    end = sentence_break + 2  # Include the period and space
                else:
                    # Look for word break
                    word_break = text.rfind(" ", search_start, search_end)
                    if word_break != -1 and word_break > start + chunk_size // 2:
                        end = word_break + 1  # Include the space
        
        # Create chunk
        chunk_text = text[start:end].strip()
        if chunk_text:
            # Ensure chunk text isn't too large (defensive check)
            if len(chunk_text) > chunk_size * 2:
                logger.warning(f"Unusually large chunk detected ({len(chunk_text)} chars), truncating")
                chunk_text = chunk_text[:chunk_size]
            
            chunks.append({
                "text": chunk_text,
                "type": "FixedSizeChunk",
                "metadata": {
                    "filename": filename,
                    "chunk_index": len(chunks),
                    "chunking_strategy": ChunkingStrategy.FIXED_SIZE,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "start_char": start,
                    "end_char": end,
                    **{f"doc_{k}": v for k, v in metadata.items()}
                }
            })
        
        # Move start position for next chunk, considering overlap
        new_start = end - chunk_overlap
        
        # Ensure we're making progress to avoid infinite loops
        if new_start <= start:
            logger.warning(f"Chunking not making progress at position {start}, forcing advance")
            new_start = start + max(1, chunk_size // 10)  # Force progress by at least 10% of chunk size
        
        # Update start position
        start = new_start
        
        # Log progress for large documents
        if len(chunks) % 100 == 0 and len(chunks) > 0:
            logger.info(f"Created {len(chunks)} chunks so far from document {filename}")
    
    if iteration_count >= max_iterations:
        logger.warning(f"Chunking stopped after reaching maximum iterations ({max_iterations})")
    
    logger.info(f"Created {len(chunks)} fixed-size chunks from document {filename}")
    return chunks

def chunk_text_by_paragraph(
    text: str, 
    filename: str,
    metadata: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Chunk text by paragraphs
    
    Args:
        text: The text to chunk
        filename: The name of the file
        metadata: Document metadata
        
    Returns:
        List of text chunks
    """
    # Split text by double newlines (paragraphs)
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current_chunk = ""
    current_start = 0
    
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        
        # If adding this paragraph would make the chunk too large, create a new chunk
        if current_chunk and len(current_chunk) + len(para) > 2000:
            chunks.append({
                "text": current_chunk,
                "type": "ParagraphChunk",
                "metadata": {
                    "filename": filename,
                    "chunk_index": len(chunks),
                    "chunking_strategy": ChunkingStrategy.PARAGRAPH,
                    "start_char": current_start,
                    "end_char": current_start + len(current_chunk),
                    **{f"doc_{k}": v for k, v in metadata.items()}
                }
            })
            current_chunk = para
            current_start = text.find(para, current_start + 1)
        else:
            if not current_chunk:
                current_start = text.find(para)
                current_chunk = para
            else:
                current_chunk += "\n\n" + para
    
    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append({
            "text": current_chunk,
            "type": "ParagraphChunk",
            "metadata": {
                "filename": filename,
                "chunk_index": len(chunks),
                "chunking_strategy": ChunkingStrategy.PARAGRAPH,
                "start_char": current_start,
                "end_char": current_start + len(current_chunk),
                **{f"doc_{k}": v for k, v in metadata.items()}
            }
        })
    
    return chunks

def chunk_text_by_sentence(
    text: str, 
    max_chunk_size: int,
    chunk_overlap: int,
    filename: str,
    metadata: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Chunk text by sentences, grouping them to stay within max_chunk_size
    
    Args:
        text: The text to chunk
        max_chunk_size: Maximum size of text chunks in characters
        chunk_overlap: Overlap between chunks in characters
        filename: The name of the file
        metadata: Document metadata
        
    Returns:
        List of text chunks
    """
    # Simple sentence splitting pattern
    sentence_pattern = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_pattern, text)
    
    chunks = []
    current_chunk = ""
    current_sentences = []
    current_start = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # If adding this sentence would make the chunk too large, create a new chunk
        if current_chunk and len(current_chunk) + len(sentence) > max_chunk_size:
            end_char = current_start + len(current_chunk)
            
            chunks.append({
                "text": current_chunk,
                "type": "SentenceChunk",
                "metadata": {
                    "filename": filename,
                    "chunk_index": len(chunks),
                    "chunking_strategy": ChunkingStrategy.SENTENCE,
                    "sentence_count": len(current_sentences),
                    "start_char": current_start,
                    "end_char": end_char,
                    **{f"doc_{k}": v for k, v in metadata.items()}
                }
            })
            
            # Start a new chunk with overlap
            overlap_sentences = []
            overlap_text = ""
            for s in reversed(current_sentences):
                if len(overlap_text) + len(s) <= chunk_overlap:
                    overlap_sentences.insert(0, s)
                    overlap_text = " ".join(overlap_sentences)
                else:
                    break
            
            current_chunk = overlap_text + " " + sentence if overlap_text else sentence
            current_sentences = overlap_sentences + [sentence]
            current_start = end_char - len(overlap_text)
        else:
            if not current_chunk:
                current_start = text.find(sentence)
                current_chunk = sentence
                current_sentences = [sentence]
            else:
                current_chunk += " " + sentence
                current_sentences.append(sentence)
    
    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append({
            "text": current_chunk,
            "type": "SentenceChunk",
            "metadata": {
                "filename": filename,
                "chunk_index": len(chunks),
                "chunking_strategy": ChunkingStrategy.SENTENCE,
                "sentence_count": len(current_sentences),
                "start_char": current_start,
                "end_char": current_start + len(current_chunk),
                **{f"doc_{k}": v for k, v in metadata.items()}
            }
        })
    
    return chunks

def chunk_text_hybrid(
    text: str, 
    chunk_size: int, 
    chunk_overlap: int, 
    filename: str,
    metadata: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Hybrid chunking strategy that combines paragraph and fixed-size approaches
    
    Args:
        text: The text to chunk
        chunk_size: Target size of text chunks in characters
        chunk_overlap: Overlap between chunks in characters
        filename: The name of the file
        metadata: Document metadata
        
    Returns:
        List of text chunks
    """
    # First split by paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current_chunk = ""
    current_start = 0
    
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        
        # If this paragraph is very long, split it further
        if len(para) > chunk_size:
            # If we have accumulated text, add it as a chunk first
            if current_chunk:
                chunks.append({
                    "text": current_chunk,
                    "type": "HybridChunk",
                    "metadata": {
                        "filename": filename,
                        "chunk_index": len(chunks),
                        "chunking_strategy": ChunkingStrategy.HYBRID,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "start_char": current_start,
                        "end_char": current_start + len(current_chunk),
                        **{f"doc_{k}": v for k, v in metadata.items()}
                    }
                })
                current_chunk = ""
            
            # Split the long paragraph using fixed-size chunking
            para_chunks = chunk_text_fixed_size(
                para, 
                chunk_size, 
                chunk_overlap, 
                filename,
                metadata
            )
            
            # Add these chunks directly
            for chunk in para_chunks:
                chunk["type"] = "HybridChunk"
                chunk["metadata"]["chunking_strategy"] = ChunkingStrategy.HYBRID
                chunks.append(chunk)
        else:
            # If adding this paragraph would make the chunk too large, create a new chunk
            if current_chunk and len(current_chunk) + len(para) + 2 > chunk_size:
                chunks.append({
                    "text": current_chunk,
                    "type": "HybridChunk",
                    "metadata": {
                        "filename": filename,
                        "chunk_index": len(chunks),
                        "chunking_strategy": ChunkingStrategy.HYBRID,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "start_char": current_start,
                        "end_char": current_start + len(current_chunk),
                        **{f"doc_{k}": v for k, v in metadata.items()}
                    }
                })
                current_chunk = para
                current_start = text.find(para, current_start + 1)
            else:
                if not current_chunk:
                    current_start = text.find(para)
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para
    
    # Add the last chunk if there's anything left
    if current_chunk:
        chunks.append({
            "text": current_chunk,
            "type": "HybridChunk",
            "metadata": {
                "filename": filename,
                "chunk_index": len(chunks),
                "chunking_strategy": ChunkingStrategy.HYBRID,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "start_char": current_start,
                "end_char": current_start + len(current_chunk),
                **{f"doc_{k}": v for k, v in metadata.items()}
            }
        })
    
    return chunks