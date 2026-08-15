from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from app.core.config import settings

DATABASE_URL = settings.database_url

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
)
