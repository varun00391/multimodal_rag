from rag_shared.app_factory import create_service_app
from rag_shared.routers import me, query

app = create_service_app(
    service_name="query",
    routers=[query.router, me.router],
    enable_session=True,
)
