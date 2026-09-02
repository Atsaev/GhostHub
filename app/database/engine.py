from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    # NullPool в тестах: соединения не должны переживать между event loop
    # pytest и TestClient (иначе asyncpg бросает InterfaceError)
    poolclass=NullPool if not settings.db_pool else None,
)
