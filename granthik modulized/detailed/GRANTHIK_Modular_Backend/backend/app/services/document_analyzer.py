"""
Document analyzer service for analyzing document structure and content
"""
import re
import math
import statistics
from typing import Dict, List, Any, Tuple
from collections import Counter

def analyze_document_structure(text: str) -> Dict[str, Any]:
    """
    Analyze the structure of a document text
    
    Args:
        text: The document text to analyze
        
    Returns:
        Dictionary containing analysis results
    """
    # Basic text stats
    char_count = len(text)
    word_count = len(re.findall(r'\b\w+\b', text))
    
    # Split into paragraphs (non-empty lines)
    paragraphs = [p for p in text.split('\n') if p.strip()]
    paragraph_count = len(paragraphs)
    
    # Calculate paragraph lengths
    paragraph_lengths = [len(p) for p in paragraphs]
    avg_paragraph_length = statistics.mean(paragraph_lengths) if paragraph_lengths else 0
    median_paragraph_length = statistics.median(paragraph_lengths) if paragraph_lengths else 0
    max_paragraph_length = max(paragraph_lengths) if paragraph_lengths else 0
    min_paragraph_length = min(paragraph_lengths) if paragraph_lengths else 0
    
    # Calculate paragraph word counts
    paragraph_word_counts = [len(re.findall(r'\b\w+\b', p)) for p in paragraphs]
    avg_paragraph_words = statistics.mean(paragraph_word_counts) if paragraph_word_counts else 0
    median_paragraph_words = statistics.median(paragraph_word_counts) if paragraph_word_counts else 0
    
    # Split into sentences
    sentence_pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s'
    sentences = re.split(sentence_pattern, text)
    sentence_count = len(sentences)
    
    # Calculate sentence lengths
    sentence_lengths = [len(s) for s in sentences]
    avg_sentence_length = statistics.mean(sentence_lengths) if sentence_lengths else 0
    median_sentence_length = statistics.median(sentence_lengths) if sentence_lengths else 0
    max_sentence_length = max(sentence_lengths) if sentence_lengths else 0
    min_sentence_length = min(sentence_lengths) if sentence_lengths else 0
    
    # Calculate sentence word counts
    sentence_word_counts = [len(re.findall(r'\b\w+\b', s)) for s in sentences]
    avg_sentence_words = statistics.mean(sentence_word_counts) if sentence_word_counts else 0
    median_sentence_words = statistics.median(sentence_word_counts) if sentence_word_counts else 0
    
    # Detect section headers
    potential_headers = []
    for i, p in enumerate(paragraphs):
        # Check if paragraph is short and followed by longer paragraphs
        if (len(p) < 100 and len(p.split()) < 15 and 
            i < len(paragraphs) - 1 and 
            len(paragraphs[i+1]) > len(p) * 2):
            potential_headers.append(p)
    
    # Detect lists
    list_items_count = 0
    list_items = []
    list_patterns = [
        r'^\s*\d+\.\s',  # Numbered lists: 1. Item
        r'^\s*[a-z]\)\s',  # Letter lists: a) Item
        r'^\s*[\-\*\•]\s'  # Bullet lists: - Item, * Item, • Item
    ]
    
    for p in paragraphs:
        for pattern in list_patterns:
            if re.match(pattern, p):
                list_items_count += 1
                list_items.append(p)
                break
    
    # Detect tables (simple heuristic based on consistent spacing/formatting)
    table_rows = []
    for i, p in enumerate(paragraphs):
        # Check for consistent spacing that might indicate a table row
        if '  ' in p and p.count('  ') >= 2:
            # Check if there are multiple spaces with similar positions in adjacent paragraphs
            if (i > 0 and '  ' in paragraphs[i-1] and 
                abs(p.find('  ') - paragraphs[i-1].find('  ')) < 3):
                table_rows.append(p)
    
    # Detect code blocks (indented blocks with special characters)
    code_blocks = []
    code_block_indicators = ['{', '}', '()', '[]', ';', '==', '!=', '+=', '-=', '<=', '>=']
    for p in paragraphs:
        if p.startswith('    ') or p.startswith('\t'):
            # Check for code-like syntax
            if any(indicator in p for indicator in code_block_indicators):
                code_blocks.append(p)
    
    # Calculate text complexity metrics
    unique_words = len(set(re.findall(r'\b\w+\b', text.lower())))
    lexical_diversity = unique_words / word_count if word_count > 0 else 0
    
    # Detect language features
    has_math = bool(re.search(r'[=\+\-\*\/\^]+[\d\.]+', text))
    has_urls = bool(re.search(r'https?://\S+', text))
    has_emails = bool(re.search(r'\S+@\S+\.\S+', text))
    
    # Compile results
    return {
        "text_stats": {
            "char_count": char_count,
            "word_count": word_count,
            "unique_words": unique_words,
            "lexical_diversity": lexical_diversity,
            "paragraph_count": paragraph_count,
            "sentence_count": sentence_count,
        },
        "paragraph_stats": {
            "count": paragraph_count,
            "avg_length": avg_paragraph_length,
            "median_length": median_paragraph_length,
            "max_length": max_paragraph_length,
            "min_length": min_paragraph_length,
            "avg_words": avg_paragraph_words,
            "median_words": median_paragraph_words,
        },
        "sentence_stats": {
            "count": sentence_count,
            "avg_length": avg_sentence_length,
            "median_length": median_sentence_length,
            "max_length": max_sentence_length,
            "min_length": min_sentence_length,
            "avg_words": avg_sentence_words,
            "median_words": median_sentence_words,
        },
        "structure": {
            "potential_headers_count": len(potential_headers),
            "list_items_count": list_items_count,
            "table_rows_count": len(table_rows),
            "code_blocks_count": len(code_blocks),
        },
        "features": {
            "has_math": has_math,
            "has_urls": has_urls,
            "has_emails": has_emails,
        },
        "sample": {
            "headers": potential_headers[:5],
            "list_items": list_items[:5],
            "table_rows": table_rows[:5],
            "code_blocks": code_blocks[:5],
        }
    }

def get_chunking_recommendations(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate chunking recommendations based on document analysis
    
    Args:
        analysis: Document analysis results
        
    Returns:
        Dictionary containing chunking recommendations
    """
    text_stats = analysis["text_stats"]
    paragraph_stats = analysis["paragraph_stats"]
    sentence_stats = analysis["sentence_stats"]
    structure = analysis["structure"]
    
    # Determine document type based on analysis
    doc_type = "general"
    doc_type_confidence = 0.5
    
    # Check for technical document
    if structure["code_blocks_count"] > 0 or analysis["features"]["has_math"]:
        doc_type = "technical"
        doc_type_confidence = min(0.5 + (structure["code_blocks_count"] / 10), 0.9)
    
    # Check for structured document with many headers and lists
    if (structure["potential_headers_count"] > 5 and 
        structure["list_items_count"] > 10):
        doc_type = "structured"
        doc_type_confidence = min(0.5 + (structure["potential_headers_count"] / 20), 0.9)
    
    # Check for narrative text (few headers, long paragraphs)
    if (structure["potential_headers_count"] < 3 and 
        paragraph_stats["avg_length"] > 500 and
        paragraph_stats["count"] > 10):
        doc_type = "narrative"
        doc_type_confidence = min(0.5 + (paragraph_stats["avg_length"] / 1000), 0.9)
    
    # Determine optimal chunking strategy
    strategy = "hybrid"  # Default strategy
    strategy_reason = "Balanced approach suitable for most documents"
    
    if doc_type == "technical":
        if structure["code_blocks_count"] > 10:
            strategy = "paragraph"
            strategy_reason = "Technical document with code blocks - paragraph chunking preserves code structure"
        else:
            strategy = "hybrid"
            strategy_reason = "Technical document with mixed content - hybrid chunking provides balance"
    
    elif doc_type == "structured":
        if structure["list_items_count"] > 20:
            strategy = "paragraph"
            strategy_reason = "Highly structured document - paragraph chunking preserves document structure"
        else:
            strategy = "hybrid"
            strategy_reason = "Structured document - hybrid chunking balances structure and context"
    
    elif doc_type == "narrative":
        if sentence_stats["avg_length"] > 100:
            strategy = "fixed_size"
            strategy_reason = "Narrative text with long sentences - fixed size chunking provides consistent chunks"
        elif paragraph_stats["avg_length"] > 1000:
            strategy = "sentence"
            strategy_reason = "Narrative text with very long paragraphs - sentence chunking prevents oversized chunks"
        else:
            strategy = "hybrid"
            strategy_reason = "Narrative text - hybrid chunking balances context and retrieval precision"
    
    # Determine optimal chunk size
    chunk_size = 1000  # Default size
    
    if doc_type == "technical":
        # Technical documents often benefit from smaller chunks for precision
        chunk_size = 800
    elif doc_type == "structured":
        # Structured documents work well with medium chunks
        chunk_size = 1000
    elif doc_type == "narrative":
        # Narrative text often benefits from larger chunks for context
        chunk_size = 1200
    
    # Adjust based on sentence length
    if sentence_stats["avg_length"] > 150:
        chunk_size = max(chunk_size, int(sentence_stats["avg_length"] * 8))
    elif sentence_stats["avg_length"] < 50:
        chunk_size = min(chunk_size, int(sentence_stats["avg_length"] * 20))
    
    # Determine optimal chunk overlap
    chunk_overlap = int(chunk_size * 0.2)  # Default 20% overlap
    
    # Adjust overlap based on document characteristics
    if doc_type == "technical" or structure["code_blocks_count"] > 5:
        # Technical documents benefit from higher overlap
        chunk_overlap = int(chunk_size * 0.3)
    elif doc_type == "narrative" and paragraph_stats["avg_length"] > 800:
        # Long narrative paragraphs benefit from higher overlap
        chunk_overlap = int(chunk_size * 0.25)
    
    return {
        "document_type": {
            "type": doc_type,
            "confidence": doc_type_confidence,
        },
        "chunking": {
            "recommended_strategy": strategy,
            "reason": strategy_reason,
            "recommended_chunk_size": chunk_size,
            "recommended_chunk_overlap": chunk_overlap,
        }
    }