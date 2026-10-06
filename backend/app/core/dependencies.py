from typing import Generator, Optional
from fastapi import Header, Query, Depends
from app.core.config import Settings, get_settings


class CommonQueryParams:
    """
    Reusable query parameter dependency for pagination and filtering.
    """
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
        search: Optional[str] = Query(None, description="Search query string"),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
        order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order ('asc' or 'desc')"),
    ):
        self.page = page
        self.page_size = page_size
        self.search = search
        self.sort_by = sort_by
        self.order = order
        self.offset = (page - 1) * page_size
        self.limit = page_size


def get_current_settings(
    settings: Settings = Depends(get_settings),
) -> Settings:
    """
    Dependency to inject application settings into route handlers.
    """
    return settings


def get_request_id(
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
) -> Optional[str]:
    """
    Dependency to extract or propagate client request ID for distributed tracing.
    """
    return x_request_id


from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.database.session import async_session_factory, sync_session_factory


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for asynchronous database sessions.
    Automatically handles session commit/rollback and cleanup.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency generator for synchronous database sessions.
    Useful for synchronous route handlers or integration scripts.
    """
    with sync_session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def get_current_user() -> None:
    """
    Dependency placeholder for user authentication / JWT token validation.
    Will return authenticated user object when auth service is configured.
    """
    raise NotImplementedError("Auth dependency not yet configured.")
