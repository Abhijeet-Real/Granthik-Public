from langchain.embeddings import OllamaEmbeddings
from langchain.vectorstores import Chroma
from langchain.schema import Document
import os

EMBED_MODEL = "nomic-embed-text"  # Choose the best Ollama-supported embedding model
PERSIST_DIR = "vectorstore/chroma"

embedding = OllamaEmbeddings(model=EMBED_MODEL)

def create_vectorstore(docs: list[str], metadatas: list[dict] = None):
    os.makedirs(PERSIST_DIR, exist_ok=True)
    doc_objs = [Document(page_content=text, metadata=meta or {}) for text, meta in zip(docs, metadatas or [{}]*len(docs))]
    vs = Chroma.from_documents(doc_objs, embedding=embedding, persist_directory=PERSIST_DIR)
    vs.persist()
    return {"status": "stored", "count": len(docs)}

def query_vectorstore(query: str, k: int = 5):
    vs = Chroma(persist_directory=PERSIST_DIR, embedding_function=embedding)
    return vs.similarity_search(query, k=k)