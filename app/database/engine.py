from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

DATABASE_URL = settings.database_url

# для sqlite каждый сеанс открывает своё соединение,
# чтобы не было проблем с привязкой соединений к event loop
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    poolclass=NullPool if DATABASE_URL.startswith("sqlite") else None,
)
