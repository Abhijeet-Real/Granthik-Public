import requests
from typing import Optional, Dict, Any, List
import json
from app.core.config import settings
from langchain_community.llms import Ollama
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate

def llm_query(model: str, prompt: str, max_tokens: Optional[int] = None, system_prompt: Optional[str] = None) -> str:
    """
    Query the LLM with a prompt and optional system prompt
    
    Args:
        model: The model to use
        prompt: The prompt to send to the model
        max_tokens: Maximum number of tokens to generate
        system_prompt: Optional system prompt to guide the model's behavior
    
    Returns:
        The model's response
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"Querying LLM with model: {model}, prompt length: {len(prompt)}")
    if system_prompt:
        logger.info(f"Using system prompt, length: {len(system_prompt)}")
    
    if max_tokens is None:
        max_tokens = settings.MAX_TOKENS
    
    try:
        # First try using LangChain's Ollama integration
        try:
            logger.info(f"Attempting to use LangChain Ollama integration with base URL: {settings.OLLAMA_URL}")
            # Extract base URL without the /api/generate part
            base_url = settings.OLLAMA_URL
            if base_url.endswith("/api/generate"):
                base_url = base_url.replace("/api/generate", "")
            elif base_url.endswith("/generate"):
                base_url = base_url.replace("/generate", "")
            elif base_url.endswith("/api"):
                base_url = base_url.replace("/api", "")
                
            logger.info(f"Using Ollama base URL: {base_url}")
            
            # Initialize Ollama with LangChain
            ollama = Ollama(
                base_url=base_url,
                model=model,
                temperature=0.1,
                num_ctx=4096,
                timeout=60
            )
            
            # Generate response
            if system_prompt:
                # Use system prompt with LangChain
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ]
                response = ollama.invoke(messages)
                logger.info(f"Received response from LangChain Ollama with system prompt, length: {len(str(response))}")
                
                # Handle different response types
                if hasattr(response, 'content'):
                    # If it's a message object
                    return response.content
                else:
                    # If it's a string or other type
                    return str(response)
            else:
                # Use regular prompt
                response = ollama.invoke(prompt)
                logger.info(f"Received response from LangChain Ollama, length: {len(str(response))}")
                
                # Handle different response types
                if hasattr(response, 'content'):
                    # If it's a message object
                    return response.content
                else:
                    # If it's a string or other type
                    return str(response)
        except Exception as lc_error:
            logger.warning(f"LangChain Ollama integration failed: {str(lc_error)}. Falling back to direct API call.")
            
        # Fall back to direct API call
        logger.info(f"Sending request to Ollama at: {settings.OLLAMA_URL}")
        # Adjust the URL to use the correct endpoint
        url = settings.OLLAMA_URL
        if not url.endswith("/generate"):
            url = f"{url}/generate"
        
        logger.info(f"Using adjusted URL: {url}")
        
        # Prepare request payload
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "max_tokens": max_tokens
        }
        
        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt
            logger.info("Added system prompt to Ollama API request")
        
        r = requests.post(
            url,
            json=payload,
            timeout=60  # Increase timeout for larger responses
        )
        r.raise_for_status()
        
        # Extract response from JSON
        response_data = r.json()
        if isinstance(response_data, dict):
            response = response_data.get("response", "").strip()
        else:
            # Handle unexpected response format
            response = str(response_data)
            
        logger.info(f"Received response from Ollama API, length: {len(response)}")
        return response
    except Exception as e:
        # Log the error
        logger.error(f"LLM error: {str(e)}")
        
        # Return a mock response for development when Ollama is not available
        if "404" in str(e) or "connection" in str(e).lower():
            logger.warning("Ollama service not available, using mock response")
            
            # Different mock responses based on the prompt content
            if "summarize" in prompt.lower() or "summary" in prompt.lower():
                mock_response = "This is a mock document summary. The document discusses key points about the topic at hand, including important facts, figures, and conclusions."
            elif "question" in prompt.lower() or "?" in prompt:
                mock_response = "This is a mock answer to your question. In a real environment with Ollama running, you would receive a proper response based on the document content."
            else:
                mock_response = "This is a mock response from the AI. For full functionality, please ensure Ollama is running and properly configured."
                
            logger.info(f"Using mock response: {mock_response}")
            return mock_response
        else:
            # Return a fallback error response
            fallback_response = (
                "I'm sorry, but I couldn't generate a response at this time. "
                "The Ollama service might not be available. "
                f"Error details: {str(e)}"
            )
            logger.info(f"Using fallback response: {fallback_response}")
            return fallback_response

def create_conversational_chain(vectorstore, model_name=None):
    """
    Create a conversational retrieval chain for RAG
    
    Args:
        vectorstore: The vector store to use for retrieval
        model_name: The name of the LLM model to use
        
    Returns:
        A conversational retrieval chain
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    if model_name is None:
        model_name = settings.DEFAULT_MODEL
    
    logger.info(f"Creating conversational chain with model: {model_name}")
    
    try:
        # Extract base URL without the /api/generate part
        base_url = settings.OLLAMA_URL
        if base_url.endswith("/api/generate"):
            base_url = base_url.replace("/api/generate", "")
        elif base_url.endswith("/generate"):
            base_url = base_url.replace("/generate", "")
        elif base_url.endswith("/api"):
            base_url = base_url.replace("/api", "")
            
        # Initialize Ollama with LangChain
        llm = Ollama(
            base_url=base_url,
            model=model_name,
            temperature=0.1,
            num_ctx=4096,
            timeout=60
        )
        
        # Create memory for conversation history
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Create custom prompt templates
        qa_template = """
        You are GRANTHIK, an advanced AI assistant specialized in document analysis and question answering.
        
        CONTEXT INFORMATION FROM DOCUMENTS:
        {context}
        
        CHAT HISTORY:
        {chat_history}
        
        USER QUESTION: {question}
        
        INSTRUCTIONS:
        1. Analyze the provided document chunks carefully and thoroughly.
        2. Answer the question based ONLY on the information in the document chunks.
        3. If the answer is not in the document chunks, clearly state: "I don't have enough information to answer this question based on the provided documents."
        4. Provide a comprehensive, accurate, and well-structured answer.
        5. Include specific details, quotes, and references from the documents when relevant.
        6. Do not make up information or use knowledge outside of the provided chunks.
        7. If the document chunks contain conflicting information, acknowledge this and present the different perspectives.
        8. Format your answer for readability with paragraphs, bullet points, or numbered lists as appropriate.
        
        YOUR RESPONSE:
        """
        
        QA_PROMPT = PromptTemplate(
            template=qa_template, 
            input_variables=["context", "question", "chat_history"]
        )
        
        # Create the chain
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(
                search_kwargs={"k": settings.TOP_K}
            ),
            memory=memory,
            combine_docs_chain_kwargs={"prompt": QA_PROMPT},
            return_source_documents=True,
            verbose=True
        )
        
        logger.info("Successfully created conversational chain")
        return chain
    
    except Exception as e:
        logger.error(f"Error creating conversational chain: {str(e)}")
        raise