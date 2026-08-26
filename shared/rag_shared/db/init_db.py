from rag_shared.models import entities  # noqa: F401
from rag_shared.db.base import Base
from rag_shared.db.session import engine


async def init_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
