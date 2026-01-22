"""FastAPI приложение для Gepvi Reports"""
import logging.config

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings.logs import LogsConfig
from settings.config import AppConfig, STAND
from web.routes.reports import router as reports_router
from web.routes.tasks import router as tasks_router
from web.routes.notifications import router as notifications_router
from web.middleware import APIKeyMiddleware
from app.utils.error_handler import global_exception_handler, create_error_responses

# Настраиваем логирование
logging.config.dictConfig(LogsConfig.LOGGING)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения

sentry_sdk.init(
    dsn=AppConfig.SENTRY_DSN,
    send_default_pii=True,
    environment=STAND
)

app = FastAPI(
    title="Gepvi Reports API",
    description="Reporting and notification service with AI-powered analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Добавляем глобальный обработчик исключений
app.add_exception_handler(Exception, global_exception_handler)

# API Key middleware (должен быть первым)
if AppConfig.API_KEY:
    app.add_middleware(APIKeyMiddleware, api_key=AppConfig.API_KEY)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутов
app.include_router(
    reports_router,
    prefix="/reports",
    tags=["reports"],
    responses=create_error_responses()
)

app.include_router(
    tasks_router,
    prefix="/tasks",
    tags=["tasks"],
    responses=create_error_responses()
)

app.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["notifications"],
    responses=create_error_responses()
)


@app.get("/", tags=["health"])
async def root():
    return {
        "status": "ok",
        "message": "Gepvi Reports API is running",
        "version": "1.0.0"
    }


@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "gepvi_reports"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "web.main:app",
        host="0.0.0.0",
        port=AppConfig.PORT,
        reload=True
    )
