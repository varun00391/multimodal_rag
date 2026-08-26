from app.models import entities  # noqa: F401
from app.db.base import Base
from app.db.session import engine


async def init_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
