from rag_shared.app_factory import create_service_app
from rag_shared.routers.auth import router as auth_router

app = create_service_app(
    service_name="auth",
    routers=[auth_router],
    init_db=True,
    enable_session=True,
)
