from rag_shared.app_factory import create_service_app
from rag_shared.routers import admins, departments, users

app = create_service_app(
    service_name="user-management",
    routers=[departments.router, admins.router, users.router],
    enable_session=True,
)
