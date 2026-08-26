from rag_shared.app_factory import create_service_app
from rag_shared.routers.documents import router as documents_router

app = create_service_app(
    service_name="documents",
    routers=[documents_router],
    init_db=True,
    enable_session=True,
)
