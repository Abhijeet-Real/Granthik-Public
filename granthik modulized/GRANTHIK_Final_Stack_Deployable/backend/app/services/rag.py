"""
Enhanced RAG (Retrieval Augmented Generation) service for GRANTHIK
"""
import logging
from typing import List, Dict, Any, Optional
import json

from app.core.config import settings
from app.services.llm import llm_query, create_conversational_chain
from app.services.vector_store import get_vectorstore
from langchain.chains import ConversationalRetrievalChain
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger("uvicorn")

class RAGService:
    """
    Enhanced RAG service with multiple retrieval strategies and robust error handling
    """
    
    def __init__(self, model: str = None):
        """
        Initialize the RAG service
        
        Args:
            model: The LLM model to use (defaults to settings.DEFAULT_MODEL)
        """
        self.model = model or settings.DEFAULT_MODEL
        self.vectorstore = get_vectorstore()
        self._chain = None
        logger.info(f"Initialized RAG service with model: {self.model}")
    
    @property
    def chain(self):
        """Lazy-load the conversational chain"""
        if self._chain is None:
            try:
                self._chain = create_conversational_chain(self.vectorstore, self.model)
            except Exception as e:
                logger.error(f"Failed to create conversational chain: {str(e)}")
                self._chain = None
        return self._chain
    
    def query(
        self, 
        query: str, 
        file_ids: Optional[List[str]] = None,
        top_k: int = 10,
        date_range: Optional[Dict[str, str]] = None,
        retrieval_strategy: str = "hybrid"
    ) -> Dict[str, Any]:
        """
        Process a query using RAG
        
        Args:
            query: The user query
            file_ids: Optional list of file IDs to search within
            top_k: Number of chunks to retrieve
            date_range: Optional date range filter
            retrieval_strategy: Retrieval strategy to use (hybrid, semantic, keyword, ensemble)
            
        Returns:
            Dictionary with answer and sources
        """
        logger.info(f"Processing RAG query: '{query}' with strategy: {retrieval_strategy}")
        logger.info(f"File IDs filter: {file_ids}")
        
        # Validate file_ids to ensure they're not empty strings
        if file_ids:
            file_ids = [fid for fid in file_ids if fid and fid.strip()]
            logger.info(f"Filtered file_ids: {file_ids}")
            
            # If all file_ids were invalid, set to None
            if not file_ids:
                file_ids = None
                logger.warning("All provided file_ids were invalid, searching across all documents")
        
        try:
            # First try using the conversational chain
            if self.chain is not None:
                try:
                    logger.info("Using LangChain ConversationalRetrievalChain for RAG")
                    
                    # Build filter conditions for metadata filtering
                    filter_dict = {}
                    
                    # Apply document filter if specified
                    if file_ids:
                        filter_dict["file_id"] = {"$in": file_ids}
                        logger.info(f"Applied file_id filter to chain: {filter_dict}")
                    
                    # Apply date range filter if specified
                    if date_range:
                        date_conditions = {}
                        if date_range.get("start"):
                            date_conditions["$gte"] = date_range["start"]
                        if date_range.get("end"):
                            date_conditions["$lte"] = date_range["end"]
                        
                        if date_conditions:
                            filter_dict["date"] = date_conditions
                    
                    # Set search kwargs with filter if needed
                    search_kwargs = {"k": top_k}
                    if filter_dict:
                        search_kwargs["filter"] = filter_dict
                    
                    # Update retriever with filters
                    self.chain.retriever.search_kwargs.update(search_kwargs)
                    logger.info(f"Updated retriever search kwargs: {self.chain.retriever.search_kwargs}")
                    
                    # Execute the chain
                    result = self.chain({"question": query})
                    
                    # Extract answer and source documents
                    answer = result.get("answer", "")
                    source_docs = result.get("source_documents", [])
                    
                    # Verify that sources match the file_id filter if specified
                    if file_ids:
                        filtered_source_docs = []
                        for doc in source_docs:
                            doc_file_id = doc.metadata.get("file_id")
                            if doc_file_id in file_ids:
                                filtered_source_docs.append(doc)
                            else:
                                logger.warning(f"Removing source doc with file_id {doc_file_id} not in requested file_ids {file_ids}")
                        
                        if filtered_source_docs:
                            source_docs = filtered_source_docs
                        else:
                            logger.warning("No source docs matched the file_id filter, falling back to traditional approach")
                            raise ValueError("No matching documents found in conversational chain results")
                    
                    # Format sources for response
                    formatted_sources = []
                    for doc in source_docs:
                        formatted_sources.append({
                            "content": doc.page_content,
                            "metadata": doc.metadata
                        })
                    
                    return {
                        "answer": answer,
                        "sources": formatted_sources
                    }
                    
                except Exception as chain_error:
                    logger.error(f"Error using conversational chain: {str(chain_error)}")
                    logger.info("Falling back to traditional RAG approach")
            
            # Fall back to traditional approach
            # Build filter conditions
            filter_conditions = {}
            
            # Apply document filter if specified
            if file_ids:
                filter_conditions["file_id"] = {"$in": file_ids}
                logger.info(f"Applied file_id filter to traditional approach: {filter_conditions}")
            
            # Apply date range filter if specified
            if date_range:
                date_conditions = {}
                if date_range.get("start"):
                    date_conditions["$gte"] = date_range["start"]
                if date_range.get("end"):
                    date_conditions["$lte"] = date_range["end"]
                
                if date_conditions:
                    filter_conditions["date"] = date_conditions
            
            # Get relevant chunks based on retrieval strategy
            chunks = self._retrieve_chunks(
                query=query,
                filter_conditions=filter_conditions,
                top_k=top_k,
                strategy=retrieval_strategy
            )
            
            if not chunks:
                logger.warning(f"No relevant chunks found for query: '{query}'")
                return {
                    "answer": "I couldn't find any relevant information to answer your question. Please try rephrasing your query or check if the documents you're referring to are available.",
                    "sources": []
                }
            
            # Format chunks for the prompt
            chunks_text = "\n\n".join([
                f"Document: {chunk['metadata'].get('filename', 'Unknown')}\n"
                f"Content: {chunk['content']}" 
                for chunk in chunks
            ])
            
            # Create a comprehensive prompt for the LLM
            prompt = f"""You are GRANTHIK, an advanced AI assistant specialized in document analysis and question answering.
            
            USER QUESTION: {query}
            
            CONTEXT INFORMATION FROM DOCUMENTS:
            {chunks_text}
            
            INSTRUCTIONS:
            1. Analyze the provided document chunks carefully and thoroughly.
            2. Answer the question based ONLY on the information in the document chunks.
            3. If the answer is not in the document chunks, clearly state: "I don't have enough information to answer this question based on the provided documents."
            4. Provide a comprehensive, accurate, and well-structured answer.
            5. Include specific details, quotes, and references from the documents when relevant.
            6. Do not make up information or use knowledge outside of the provided chunks.
            7. If the document chunks contain conflicting information, acknowledge this and present the different perspectives.
            8. Format your answer for readability with paragraphs, bullet points, or numbered lists as appropriate.
            
            YOUR RESPONSE:"""
            
            # Get answer from LLM
            answer = llm_query(self.model, prompt)
            
            # Format sources for response
            formatted_sources = []
            for chunk in chunks:
                formatted_sources.append({
                    "content": chunk["content"],
                    "metadata": chunk["metadata"]
                })
            
            return {
                "answer": answer,
                "sources": formatted_sources
            }
            
        except Exception as e:
            logger.error(f"Error in RAG query: {str(e)}")
            return {
                "answer": f"I encountered an error while processing your query. Please try again later. Error details: {str(e)}",
                "sources": []
            }
    
    def _retrieve_chunks(
        self, 
        query: str, 
        filter_conditions: Dict[str, Any],
        top_k: int = 10,
        strategy: str = "hybrid"
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks using the specified strategy
        
        Args:
            query: The user query
            filter_conditions: Filter conditions for the retrieval
            top_k: Number of chunks to retrieve
            strategy: Retrieval strategy to use
            
        Returns:
            List of relevant chunks
        """
        logger.info(f"Retrieving chunks with strategy: {strategy}")
        
        try:
            if strategy == "semantic":
                # Pure semantic search
                return self._semantic_search(query, filter_conditions, top_k)
            elif strategy == "keyword":
                # Keyword-based search
                return self._keyword_search(query, filter_conditions, top_k)
            elif strategy == "ensemble":
                # Ensemble approach (combine semantic and keyword)
                return self._ensemble_search(query, filter_conditions, top_k)
            else:
                # Default to hybrid approach
                return self._hybrid_search(query, filter_conditions, top_k)
        except Exception as e:
            logger.error(f"Error retrieving chunks: {str(e)}")
            # Fall back to basic semantic search
            try:
                return self._basic_search(query, filter_conditions, top_k)
            except Exception as inner_e:
                logger.error(f"Error in fallback retrieval: {str(inner_e)}")
                return []
    
    def _semantic_search(
        self, 
        query: str, 
        filter_conditions: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using vector embeddings
        """
        logger.info(f"Performing semantic search for: '{query}'")
        logger.info(f"Filter conditions: {filter_conditions}")
        
        try:
            # First try direct collection search for better metadata filtering
            collection = self.vectorstore.collection
            
            # Ensure we're using the right format for ChromaDB filters
            chroma_filter = self._format_filter_for_chroma(filter_conditions)
            logger.info(f"Formatted ChromaDB filter: {chroma_filter}")
            
            # Query the collection directly
            result = collection.query(
                query_texts=[query],
                where=chroma_filter,
                n_results=top_k
            )
            
            # Format results
            results = []
            for i, doc in enumerate(result.get("documents", [])[0]):
                if i < len(result.get("metadatas", [])[0]):
                    results.append({
                        "content": doc,
                        "metadata": result["metadatas"][0][i],
                        "retrieval_method": "semantic"
                    })
            
            logger.info(f"Direct ChromaDB semantic search returned {len(results)} results")
            
            # If we got results, return them
            if results:
                return results
                
            # Otherwise fall back to retriever approach
            logger.info("No results from direct ChromaDB query, falling back to retriever")
        except Exception as e:
            logger.warning(f"Error in direct ChromaDB query: {str(e)}, falling back to retriever")
        
        # Configure retriever with filters
        retriever = self.vectorstore.as_retriever(search_kwargs={
            "k": top_k * 2,  # Get more candidates for filtering
            "filter": filter_conditions if filter_conditions else None
        })
        
        # Get relevant documents
        docs = retriever.get_relevant_documents(query)
        
        # Format results
        results = []
        for doc in docs[:top_k]:
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "retrieval_method": "semantic"
            })
        
        logger.info(f"Retriever-based semantic search returned {len(results)} results")
        return results
        
    def _format_filter_for_chroma(self, filter_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format filter conditions for ChromaDB
        
        ChromaDB has specific filter syntax requirements
        """
        if not filter_conditions:
            return {}
            
        # Handle file_id filter specifically
        if "file_id" in filter_conditions:
            file_id_filter = filter_conditions["file_id"]
            
            # Handle $in operator for file_ids
            if isinstance(file_id_filter, dict) and "$in" in file_id_filter:
                file_ids = file_id_filter["$in"]
                if len(file_ids) == 1:
                    # Single file ID
                    return {"file_id": file_ids[0]}
                else:
                    # Multiple file IDs
                    return {"$or": [{"file_id": file_id} for file_id in file_ids]}
            else:
                # Direct file_id match
                return {"file_id": file_id_filter}
                
        # For other filters, pass through as is
        return filter_conditions
    
    def _keyword_search(
        self, 
        query: str, 
        filter_conditions: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform keyword-based search
        """
        logger.info(f"Performing keyword search for: '{query}'")
        logger.info(f"Filter conditions: {filter_conditions}")
        
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        logger.info(f"Extracted keywords: {keywords}")
        
        if not keywords:
            logger.warning("No keywords extracted, falling back to basic search")
            return self._basic_search(query, filter_conditions, top_k)
        
        # Get collection
        collection = self.vectorstore.collection
        
        # Format filter for ChromaDB
        chroma_filter = self._format_filter_for_chroma(filter_conditions)
        
        # Build keyword filter for document content
        content_conditions = []
        for keyword in keywords:
            if len(keyword) > 2:  # Only use keywords with more than 2 characters
                content_conditions.append({
                    "content_preview": {"$contains": keyword.lower()}
                })
        
        # Combine document filter with keyword filter
        if content_conditions:
            if chroma_filter:
                # If we have both document and keyword filters, combine them
                combined_filter = {
                    "$and": [
                        chroma_filter,
                        {"$or": content_conditions}
                    ]
                }
            else:
                # If we only have keyword filters
                combined_filter = {"$or": content_conditions}
        else:
            # If no valid keywords, just use the document filter
            combined_filter = chroma_filter
            
        logger.info(f"Combined filter for keyword search: {combined_filter}")
        
        try:
            # Query the collection
            result = collection.query(
                query_texts=[query] if query else None,
                where=combined_filter,
                n_results=top_k
            )
            
            # Format results
            results = []
            for i, doc in enumerate(result.get("documents", [])[0]):
                if i < len(result.get("metadatas", [])[0]):
                    results.append({
                        "content": doc,
                        "metadata": result["metadatas"][0][i],
                        "retrieval_method": "keyword"
                    })
            
            logger.info(f"Keyword search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in keyword search: {str(e)}")
            # Fall back to basic search
            logger.info("Falling back to basic search")
            return self._basic_search(query, filter_conditions, top_k)
    
    def _ensemble_search(
        self, 
        query: str, 
        filter_conditions: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform ensemble search (combine semantic and keyword)
        """
        logger.info(f"Performing ensemble search for: '{query}'")
        
        # Get results from both methods
        semantic_results = self._semantic_search(query, filter_conditions, top_k)
        keyword_results = self._keyword_search(query, filter_conditions, top_k)
        
        # Combine and deduplicate results
        combined_results = {}
        
        # Add semantic results with higher priority
        for result in semantic_results:
            key = f"{result['metadata'].get('file_id', '')}_{result['metadata'].get('chunk_index', '')}"
            result["score"] = 1.0  # Base score for semantic results
            combined_results[key] = result
        
        # Add keyword results
        for result in keyword_results:
            key = f"{result['metadata'].get('file_id', '')}_{result['metadata'].get('chunk_index', '')}"
            if key in combined_results:
                # If already in results, increase score
                combined_results[key]["score"] += 0.5
                combined_results[key]["retrieval_method"] = "ensemble"
            else:
                # Otherwise add with lower base score
                result["score"] = 0.5
                combined_results[key] = result
        
        # Sort by score and limit to top_k
        results = list(combined_results.values())
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        logger.info(f"Ensemble search returned {len(results[:top_k])} results")
        return results[:top_k]
    
    def _hybrid_search(
        self, 
        query: str, 
        filter_conditions: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (semantic search with keyword reranking)
        """
        logger.info(f"Performing hybrid search for: '{query}'")
        
        # Get semantic search results
        semantic_results = self._semantic_search(query, filter_conditions, top_k * 2)
        
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        
        # Rerank results based on keyword presence
        for result in semantic_results:
            score = 0
            content = result["content"].lower()
            for keyword in keywords:
                if keyword.lower() in content:
                    score += 1
            result["keyword_score"] = score
        
        # Sort by combined score (semantic + keyword)
        semantic_results.sort(key=lambda x: x.get("keyword_score", 0), reverse=True)
        
        # Update retrieval method
        for result in semantic_results[:top_k]:
            result["retrieval_method"] = "hybrid"
        
        logger.info(f"Hybrid search returned {len(semantic_results[:top_k])} results")
        return semantic_results[:top_k]
    
    def _basic_search(
        self, 
        query: str, 
        filter_conditions: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform basic search as a fallback
        """
        logger.info(f"Performing basic search for: '{query}'")
        logger.info(f"Filter conditions: {filter_conditions}")
        
        # Get collection
        collection = self.vectorstore.collection
        
        # Format filter for ChromaDB
        chroma_filter = self._format_filter_for_chroma(filter_conditions)
        logger.info(f"Formatted ChromaDB filter for basic search: {chroma_filter}")
        
        try:
            # Query the collection
            result = collection.query(
                query_texts=[query] if query else None,
                where=chroma_filter if chroma_filter else None,
                n_results=top_k
            )
            
            # Format results
            results = []
            for i, doc in enumerate(result.get("documents", [])[0]):
                if i < len(result.get("metadatas", [])[0]):
                    results.append({
                        "content": doc,
                        "metadata": result["metadatas"][0][i],
                        "retrieval_method": "basic"
                    })
            
            logger.info(f"Basic search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error in basic search: {str(e)}")
            
            # Last resort: try to get any documents that match the filter
            try:
                # If we have a file_id filter, try to get documents directly by ID
                if "file_id" in filter_conditions:
                    file_id_filter = filter_conditions["file_id"]
                    file_ids = []
                    
                    if isinstance(file_id_filter, dict) and "$in" in file_id_filter:
                        file_ids = file_id_filter["$in"]
                    elif isinstance(file_id_filter, str):
                        file_ids = [file_id_filter]
                    
                    if file_ids:
                        logger.info(f"Trying to fetch documents directly by file_ids: {file_ids}")
                        all_results = []
                        
                        for file_id in file_ids:
                            try:
                                # Get documents for this file_id
                                file_result = collection.get(
                                    where={"file_id": file_id},
                                    limit=top_k
                                )
                                
                                # Add to results
                                for i, doc in enumerate(file_result.get("documents", [])):
                                    if i < len(file_result.get("metadatas", [])):
                                        all_results.append({
                                            "content": doc,
                                            "metadata": file_result["metadatas"][i],
                                            "retrieval_method": "direct_file_id"
                                        })
                            except Exception as file_error:
                                logger.error(f"Error fetching documents for file_id {file_id}: {str(file_error)}")
                        
                        if all_results:
                            logger.info(f"Direct file_id fetch returned {len(all_results)} results")
                            return all_results[:top_k]
            except Exception as direct_error:
                logger.error(f"Error in direct document fetch: {str(direct_error)}")
            
            # If all else fails, return empty results
            logger.warning("All search methods failed, returning empty results")
            return []
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract keywords from a query
        """
        # Simple keyword extraction (remove stop words and get unique terms)
        stop_words = {
            "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", 
            "be", "been", "being", "in", "on", "at", "to", "for", "with", "by",
            "about", "against", "between", "into", "through", "during", "before",
            "after", "above", "below", "from", "up", "down", "of", "off", "over",
            "under", "again", "further", "then", "once", "here", "there", "when",
            "where", "why", "how", "all", "any", "both", "each", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "s", "t", "can", "will", "just",
            "don", "should", "now", "what", "who", "whom", "this", "that", "these",
            "those", "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
            "you", "your", "yours", "yourself", "yourselves", "he", "him", "his",
            "himself", "she", "her", "hers", "herself", "it", "its", "itself",
            "they", "them", "their", "theirs", "themselves", "which", "who", "whom",
            "whose", "if", "else", "while", "as", "until", "because", "since",
            "do", "does", "did", "having", "has", "have", "had", "could", "would",
            "should", "shall", "might", "may", "must"
        }
        
        # Tokenize and filter
        words = query.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Remove duplicates while preserving order
        unique_keywords = []
        for keyword in keywords:
            if keyword not in unique_keywords:
                unique_keywords.append(keyword)
        
        return unique_keywords