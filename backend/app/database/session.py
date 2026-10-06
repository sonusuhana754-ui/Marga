from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# ------------------ Async Engine & Session Setup ------------------
# pool_pre_ping: true helps detect and drop disconnected connections automatically
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URI,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    future=True,
)

async_session_factory = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ------------------ Sync Engine & Session Setup ------------------
# Required for synchronous execution paths, such as Alembic migrations
sync_engine = create_engine(
    settings.SYNC_DATABASE_URI,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    future=True,
)

sync_session_factory = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)
