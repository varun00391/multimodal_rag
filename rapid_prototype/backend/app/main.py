from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import init_db
from app.config import settings
from app.routers import auth, chat, connectors, dashboard, documents
from app.services.rag import AVAILABLE_MODELS

app = FastAPI(
    title="Nexus Multimodal RAG",
    description="Prototype API for multimodal retrieval, connectors, and usage analytics.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["http://localhost:80", "http://frontend"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(connectors.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "models": AVAILABLE_MODELS,
        "llm_configured": bool(settings.openai_api_key),
    }
