from rag_shared.app_factory import create_service_app
from rag_shared.routers import audit, dashboard

app = create_service_app(
    service_name="dashboard",
    routers=[dashboard.router, audit.router],
    init_db=True,
    enable_session=True,
)
