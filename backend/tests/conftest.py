import os
import tempfile
from pathlib import Path

import pytest

_TEST_DB = Path(tempfile.gettempdir()) / "docqa_test.sqlite3"
_TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")
os.environ.setdefault("JWT_SECRET", "test-secret-not-used-in-production")
_TMP = Path(tempfile.mkdtemp(prefix="docqa-test-"))
os.environ["CHROMA_PERSIST_DIR"] = str(_TMP / "chroma")
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    import asyncio

    from src.db.models import Base
    from src.db.session import engine

    async def create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create())
    yield
    _TEST_DB.unlink(missing_ok=True)


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    from src.db.models import Base
    from src.db.session import async_session_maker, engine
    from src.main import app
    from src.middleware.rate_limit import reset_all_limiters

    reset_all_limiters()

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    async with async_session_maker() as session:
        await session.rollback()


@pytest.fixture
def sample_short_text():
    return "This is a short piece of text that should not be split."


@pytest.fixture
def sample_long_text():
    paragraphs = [
        f"This is paragraph number {i}. It contains several sentences about topic {i}. "
        f"The content here is designed to be long enough to require chunking. "
        f"Each paragraph discusses a different subject to test semantic boundaries."
        for i in range(50)
    ]
    return "\n\n".join(paragraphs)


@pytest.fixture
def sample_multiline_text():
    return """First section of the document.
This is part of the first section with more detail.

Second section of the document.
This section discusses a completely different topic.

Third section with conclusions.
The conclusions summarize the findings from previous sections."""


@pytest.fixture
def stub_vector_store():
    from unittest.mock import AsyncMock, MagicMock

    from src.api.deps import get_vector_store
    from src.main import app

    stub = MagicMock()
    stub.aadd_documents = AsyncMock()
    stub.adelete_by_filter = AsyncMock()

    app.dependency_overrides[get_vector_store] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_vector_store, None)
