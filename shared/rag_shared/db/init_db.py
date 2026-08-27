import asyncio

import structlog
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from rag_shared.models import entities  # noqa: F401
from rag_shared.db.base import Base
from rag_shared.db.session import engine

logger = structlog.get_logger(__name__)

# Fixed lock id so only one container bootstraps schema at a time.
_SCHEMA_INIT_LOCK_ID = 9_876_543_210


async def init_database() -> None:
    """Create tables/enums once. Safe if called concurrently or after partial init."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": _SCHEMA_INIT_LOCK_ID})
        try:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("database_initialized")
        except DBAPIError as exc:
            message = str(exc.orig).lower()
            if "already exists" in message or "duplicate key" in message:
                logger.info("database_already_initialized")
            else:
                raise
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": _SCHEMA_INIT_LOCK_ID},
            )


def main() -> None:
    asyncio.run(init_database())
    print("Database initialization complete.")


if __name__ == "__main__":
    main()
