import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.api.deps import get_async_db
from app.database.base import Base

# Use in-memory SQLite database for test execution path
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
test_session_factory = async_sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def override_get_async_db():
    """
    Overrides the async database dependency for FastAPI testing.
    Automatically creates all tables on-demand in the in-memory SQLite DB.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Mount dependency override
app.dependency_overrides[get_async_db] = override_get_async_db


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Synchronous FastAPI test client fixture.
    """
    with TestClient(app) as test_client:
        yield test_client
