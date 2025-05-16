from langchain.chat_models import ChatOllama
from langchain.vectorstores import Chroma
from langchain.embeddings import OllamaEmbeddings
from langchain.chains import RetrievalQA

# Vector search + LLM model
embedding = OllamaEmbeddings(model="nomic-embed-text")
vectorstore = Chroma(persist_directory="vectorstore/chroma", embedding_function=embedding)
rag_model = ChatOllama(model="mistral")

def answer_with_rag(question: str) -> str:
    qa_chain = RetrievalQA.from_chain_type(llm=rag_model, retriever=vectorstore.as_retriever())
    return qa_chain.run(question)

def answer_with_general_llm(prompt: str) -> str:
    return rag_model.invoke(prompt)