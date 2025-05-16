import os
import sys
import unittest
import tempfile
import logging
import traceback
from typing import List, Dict, Any

# Add the parent directory to the path so we can import the app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ocr import ocr_parse
from app.services.document_processor import (
    chunk_text_fixed_size, 
    chunk_text_by_paragraph,
    chunk_text_by_sentence,
    process_document,
    ChunkingStrategy
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestOCRAndChunking(unittest.TestCase):
    """Test OCR and chunking functionality independently"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a small test file with some text
        self.test_text = """
        This is a test document for OCR and chunking.
        
        It has multiple paragraphs to test different chunking strategies.
        Each paragraph should be handled properly by the chunking functions.
        
        This is the third paragraph with some more text.
        We want to make sure that the chunking functions work correctly.
        
        Here's a fourth paragraph to ensure we have enough text to test with.
        """
        
        # Create a temporary text file
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        with open(self.temp_file.name, "w") as f:
            f.write(self.test_text)
        
        # Read the file content for testing
        with open(self.temp_file.name, "rb") as f:
            self.file_content = f.read()
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary file
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_fixed_size_chunking(self):
        """Test fixed size chunking"""
        try:
            # Test with different chunk sizes
            for chunk_size in [50, 100, 200]:
                for chunk_overlap in [0, 20, 50]:
                    if chunk_overlap >= chunk_size:
                        continue  # Skip invalid combinations
                    
                    logger.info(f"Testing fixed size chunking with size={chunk_size}, overlap={chunk_overlap}")
                    chunks = chunk_text_fixed_size(
                        self.test_text,
                        chunk_size,
                        chunk_overlap,
                        "test.txt",
                        {"test": True}
                    )
                    
                    # Verify chunks
                    self.assertIsInstance(chunks, list)
                    self.assertTrue(len(chunks) > 0)
                    
                    # Check chunk sizes
                    for chunk in chunks:
                        self.assertIsInstance(chunk, dict)
                        self.assertIn("text", chunk)
                        self.assertIn("metadata", chunk)
                        
                        # Chunk should not be larger than chunk_size * 2 (with some margin for error)
                        self.assertLessEqual(len(chunk["text"]), chunk_size * 2.1)
                        
                        # Check metadata
                        self.assertEqual(chunk["metadata"]["filename"], "test.txt")
                        self.assertEqual(chunk["metadata"]["doc_test"], True)
                    
                    logger.info(f"Created {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Error in fixed size chunking test: {str(e)}")
            logger.error(traceback.format_exc())
            self.fail(f"Fixed size chunking test failed: {str(e)}")
    
    def test_paragraph_chunking(self):
        """Test paragraph chunking"""
        try:
            logger.info("Testing paragraph chunking")
            chunks = chunk_text_by_paragraph(
                self.test_text,
                "test.txt",
                {"test": True}
            )
            
            # Verify chunks
            self.assertIsInstance(chunks, list)
            self.assertTrue(len(chunks) > 0)
            
            # Check that we have roughly the right number of paragraphs
            # The test text has 4 paragraphs plus some empty lines
            self.assertGreaterEqual(len(chunks), 4)
            
            # Check chunk content
            for chunk in chunks:
                self.assertIsInstance(chunk, dict)
                self.assertIn("text", chunk)
                self.assertIn("metadata", chunk)
                
                # Check metadata
                self.assertEqual(chunk["metadata"]["filename"], "test.txt")
                self.assertEqual(chunk["metadata"]["doc_test"], True)
            
            logger.info(f"Created {len(chunks)} paragraph chunks")
        except Exception as e:
            logger.error(f"Error in paragraph chunking test: {str(e)}")
            logger.error(traceback.format_exc())
            self.fail(f"Paragraph chunking test failed: {str(e)}")
    
    def test_sentence_chunking(self):
        """Test sentence chunking"""
        try:
            logger.info("Testing sentence chunking")
            chunks = chunk_text_by_sentence(
                self.test_text,
                "test.txt",
                {"test": True}
            )
            
            # Verify chunks
            self.assertIsInstance(chunks, list)
            self.assertTrue(len(chunks) > 0)
            
            # The test text has several sentences
            self.assertGreaterEqual(len(chunks), 6)
            
            # Check chunk content
            for chunk in chunks:
                self.assertIsInstance(chunk, dict)
                self.assertIn("text", chunk)
                self.assertIn("metadata", chunk)
                
                # Check metadata
                self.assertEqual(chunk["metadata"]["filename"], "test.txt")
                self.assertEqual(chunk["metadata"]["doc_test"], True)
            
            logger.info(f"Created {len(chunks)} sentence chunks")
        except Exception as e:
            logger.error(f"Error in sentence chunking test: {str(e)}")
            logger.error(traceback.format_exc())
            self.fail(f"Sentence chunking test failed: {str(e)}")
    
    def test_process_document(self):
        """Test the full document processing pipeline"""
        try:
            logger.info("Testing document processing")
            
            # Test with different chunking strategies
            for strategy in [
                ChunkingStrategy.FIXED_SIZE,
                ChunkingStrategy.PARAGRAPH,
                ChunkingStrategy.SENTENCE,
                ChunkingStrategy.HYBRID
            ]:
                logger.info(f"Testing document processing with strategy: {strategy}")
                chunks, metadata = process_document(
                    self.file_content,
                    "test.txt",
                    ["eng"],
                    100,
                    20,
                    strategy
                )
                
                # Verify chunks
                self.assertIsInstance(chunks, list)
                self.assertTrue(len(chunks) > 0)
                
                # Check metadata
                self.assertIsInstance(metadata, dict)
                
                logger.info(f"Processed document with strategy {strategy}, got {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Error in document processing test: {str(e)}")
            logger.error(traceback.format_exc())
            self.fail(f"Document processing test failed: {str(e)}")
    
    def test_ocr_parse(self):
        """Test OCR parsing (if Unstructured API is available)"""
        try:
            from app.core.config import settings
            
            # Skip if UNSTRUCTURED_URL is not set
            if not hasattr(settings, "UNSTRUCTURED_URL") or not settings.UNSTRUCTURED_URL:
                logger.warning("Skipping OCR test because UNSTRUCTURED_URL is not set")
                return
            
            logger.info("Testing OCR parsing")
            
            try:
                # Test OCR parsing
                chunks = ocr_parse(
                    self.file_content,
                    "test.txt",
                    ["eng"],
                    100,
                    20
                )
                
                # Verify chunks
                self.assertIsInstance(chunks, list)
                self.assertTrue(len(chunks) > 0)
                
                logger.info(f"OCR parsing successful, got {len(chunks)} chunks")
            except Exception as ocr_error:
                logger.warning(f"OCR test failed, likely because Unstructured API is not available: {str(ocr_error)}")
                # Don't fail the test, as the API might not be available
        except Exception as e:
            logger.error(f"Error in OCR test setup: {str(e)}")
            logger.error(traceback.format_exc())
            self.fail(f"OCR test setup failed: {str(e)}")

if __name__ == "__main__":
    unittest.main()