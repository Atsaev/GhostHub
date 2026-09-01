import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="ghosthub_tests_")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("STORAGE_PATH", f"{_TMP}/storage")

import pytest  # noqa: E402
from litestar.testing import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
async def clean_db():
    from app.database.base import Base
    from app.database.engine import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
