from pathlib import Path
import sys

# Fix alembic import conflicts with local alembic directory
# Remove parent directory from sys.path temporarily
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir in sys.path:
    sys.path.remove(_parent_dir)

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Now import alembic from the installed package
from alembic import command
from alembic.config import Config

# Restore parent directory to sys.path
sys.path.insert(0, _parent_dir)

from settings.config import AppConfig
from web.main import app
from app.database import get_session
from app.models import Report, Task, Notification


@pytest.fixture(scope='session')
def db_url():
    if 'test' not in AppConfig.TEST_DB_URL:
        raise ValueError('You are trying to run tests on a prod/dev database')
    AppConfig.DB_URL = AppConfig.TEST_DB_URL  # patch settings for tests
    # API_KEY уже установлен в settings/config.py с дефолтным значением
    return AppConfig.DB_URL


# flake8: noqa WPS325
@pytest.fixture(scope='session')
def apply_migrations(db_url):
    """Применяет миграции для тестовой БД"""
    parent_dir = Path(__file__).resolve().parent.parent
    config = Config(str(parent_dir.joinpath('alembic.ini')))
    config.set_main_option('script_location', str(parent_dir.joinpath('alembic')))
    command.upgrade(config, 'head')
    yield None
    command.downgrade(config, 'base')


@pytest.fixture
def api_headers(db_url):
    """Заголовки с API ключом для тестов"""
    # db_url fixture ensures AppConfig is properly initialized
    return {"X-API-Key": AppConfig.API_KEY}


@pytest_asyncio.fixture
async def async_client(apply_migrations) -> AsyncClient:
    """Async HTTP client для тестов API"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def session(apply_migrations) -> AsyncSession:
    """Async database session для тестов"""
    async for session in get_session():
        yield session
        break  # get_session - это генератор, нам нужна только одна сессия


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db():
    """Автоматическая очистка БД после каждого теста"""
    yield
    async for session in get_session():
        try:
            await session.execute(Report.__table__.delete())
            await session.execute(Task.__table__.delete())
            await session.execute(Notification.__table__.delete())
            await session.commit()
        except Exception:
            # Игнорируем ошибки если таблицы не существуют
            await session.rollback()
        break  # get_session - это генератор, нам нужна только одна сессия
