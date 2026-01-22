"""Async database connection и session management"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from settings.config import AppConfig


# Create async engine
engine = create_async_engine(
    AppConfig.DB_URL.replace('postgresql://', 'postgresql+asyncpg://'),
    echo=AppConfig.DEBUG,
    future=True,
    poolclass=NullPool,  # Use NullPool for simplicity, adjust as needed
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency для получения DB сессии"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
