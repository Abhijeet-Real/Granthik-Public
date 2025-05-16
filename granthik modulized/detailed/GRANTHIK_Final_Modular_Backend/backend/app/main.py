from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all routes from modules
from modules.document.routes import router as document_router
from modules.ocr.routes import router as ocr_router
from modules.chunker.routes import router as chunker_router
from modules.vectorstore.routes import router as vectorstore_router
from modules.summarizer.routes import router as summarizer_router
from modules.chatbot.routes import router as chatbot_router
from modules.admin.routes import router as admin_router

app = FastAPI(title="GRANTHIK Modular API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(document_router)
app.include_router(ocr_router)
app.include_router(chunker_router)
app.include_router(vectorstore_router)
app.include_router(summarizer_router)
app.include_router(chatbot_router)
app.include_router(admin_router)

@app.get("/")
def root():
    return {"message": "GRANTHIK Modular API is up and running"}