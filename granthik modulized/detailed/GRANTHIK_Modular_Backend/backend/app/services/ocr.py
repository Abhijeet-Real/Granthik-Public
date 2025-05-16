import requests
import traceback
import os
import psutil
from typing import List, Dict, Any, Optional
from app.core.config import settings
from io import StringIO

# Maximum file size in bytes (500MB)
MAX_FILE_SIZE = 500 * 1024 * 1024

def log_memory_usage(logger, message: str = "Current memory usage"):
    """Log current memory usage"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logger.info(f"{message}: {memory_info.rss / 1024 / 1024:.2f} MB")

def ocr_parse(file_content: bytes, filename: str, langs: List[str], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Process a file with OCR using the Unstructured API and apply custom chunking
    
    Args:
        file_content: The binary content of the file
        filename: The name of the file
        langs: List of language codes for OCR
        chunk_size: Size of text chunks in characters
        chunk_overlap: Overlap between chunks in characters
    
    Returns:
        List of text chunks extracted from the document
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Processing document with OCR: {filename}, chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    
    # Check file size
    if len(file_content) > MAX_FILE_SIZE:
        logger.error(f"File too large: {len(file_content) / 1024 / 1024:.2f} MB exceeds limit of {MAX_FILE_SIZE / 1024 / 1024:.2f} MB")
        raise ValueError(f"File too large: maximum size is {MAX_FILE_SIZE / 1024 / 1024:.2f} MB")
    
    log_memory_usage(logger, "Memory usage before OCR")
    
    try:
        # Get raw elements from Unstructured API with timeout
        r = requests.post(
            settings.UNSTRUCTURED_URL,
            files={"files": (filename, file_content)},
            data={"ocr_languages": ",".join(langs)},
            timeout=120  # 2 minute timeout
        )
        r.raise_for_status()
        elements = r.json()
        
        log_memory_usage(logger, "Memory usage after OCR API call")
        
        # If custom chunking is disabled (chunk_size <= 0), return the original elements
        if chunk_size <= 0:
            logger.info(f"Using original chunks from Unstructured API: {len(elements)} chunks")
            return elements
        
        # Extract all text from elements using StringIO for efficiency
        text_buffer = StringIO()
        for element in elements:
            if "text" in element and element["text"]:
                # Sanitize text to avoid encoding issues
                sanitized_text = element["text"].encode('utf-8', errors='ignore').decode('utf-8')
                text_buffer.write(sanitized_text)
                text_buffer.write("\n\n")
        
        all_text = text_buffer.getvalue()
        text_buffer.close()  # Free memory
        
        log_memory_usage(logger, "Memory usage after text extraction")
        
        # Apply custom chunking
        chunks = []
        start = 0
        last_start = -1  # Track previous start position to detect infinite loops
        max_iterations = len(all_text) * 2  # Safety limit for iterations
        iteration_count = 0
        
        while start < len(all_text) and iteration_count < max_iterations:
            iteration_count += 1
            
            # Get chunk of text
            end = min(start + chunk_size, len(all_text))
            
            # If not at the end, try to find a good break point
            if end < len(all_text):
                # Look for paragraph break
                paragraph_break = all_text.rfind("\n\n", start, end)
                if paragraph_break != -1 and paragraph_break > start + chunk_size // 2:
                    end = paragraph_break + 2  # Include the newlines
                else:
                    # Look for sentence break
                    sentence_break = max(
                        all_text.rfind(". ", start, end),
                        all_text.rfind("! ", start, end),
                        all_text.rfind("? ", start, end)
                    )
                    if sentence_break != -1 and sentence_break > start + chunk_size // 2:
                        end = sentence_break + 2  # Include the period and space
                    else:
                        # Look for word break
                        word_break = all_text.rfind(" ", start, end)
                        if word_break != -1 and word_break > start + chunk_size // 2:
                            end = word_break + 1  # Include the space
            
            # Create chunk
            chunk_text = all_text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "type": "CustomChunk",
                    "metadata": {
                        "filename": filename,
                        "chunk_index": len(chunks),
                        "custom_chunking": True,
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap
                    }
                })
            
            # Move start position for next chunk, considering overlap
            new_start = end - chunk_overlap
            
            # Ensure we're making progress to avoid infinite loops
            if new_start <= start:
                new_start = start + 1  # Force progress by at least one character
            
            # Update start position
            start = new_start
            
            # Log progress periodically
            if len(chunks) % 100 == 0:
                log_memory_usage(logger, f"Memory usage after {len(chunks)} chunks")
        
        if iteration_count >= max_iterations:
            logger.warning(f"Chunking stopped after reaching maximum iterations ({max_iterations})")
        
        logger.info(f"Created {len(chunks)} custom chunks with size={chunk_size}, overlap={chunk_overlap}")
        return chunks
        
    except requests.exceptions.Timeout:
        error_msg = f"OCR request timed out for file: {filename}"
        logger.error(error_msg)
        raise TimeoutError(error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"OCR request failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise ConnectionError(error_msg)
    except Exception as e:
        # Log the detailed error
        error_msg = f"OCR error processing {filename}: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        raise Exception(f"Failed to process document with OCR: {str(e)}")