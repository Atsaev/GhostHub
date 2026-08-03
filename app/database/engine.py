from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from app.core.config import settings

DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"{settings.database_user}:"
    f"{settings.database_password}@"
    f"{settings.database_host}:"
    f"{settings.database_port}/"
    f"{settings.database_name}"
)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
)
