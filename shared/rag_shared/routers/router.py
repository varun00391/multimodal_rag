from fastapi import APIRouter

from rag_shared.routers import admins, audit, auth, dashboard, departments, documents, ingestion, me, query, retrieval, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(departments.router)
api_router.include_router(admins.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(ingestion.router)
api_router.include_router(retrieval.router)
api_router.include_router(me.router)
api_router.include_router(query.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
