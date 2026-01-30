"""FastAPI приложение для Gepvi Reports"""
import asyncio
import logging.config
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from settings.logs import LogsConfig
from settings.config import AppConfig, STAND
from web.routes.reports import router as reports_router
from web.routes.notifications import router as notifications_router
from web.middleware import APIKeyMiddleware
from app.utils.error_handler import global_exception_handler, create_error_responses
from app.database import get_session
from app.services import process_stuck_notifications

# Настраиваем логирование
logging.config.dictConfig(LogsConfig.LOGGING)
logger = logging.getLogger(__name__)

async def notification_retry_background_job():
    """Background job для обработки провисевших уведомлений каждую минуту"""
    logger.info("Starting notification retry background job")
    while True:
        try:
            async for session in get_session():
                await process_stuck_notifications(session)
        except Exception as e:
            logger.error("Error in notification retry background job: %s", e, exc_info=True)

        await asyncio.sleep(60)  # Запускаем каждую минуту


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup: запускаем background задачи
    background_task = asyncio.create_task(notification_retry_background_job())
    logger.info("Background tasks started")

    yield

    # Shutdown: останавливаем background задачи
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        logger.info("Background task cancelled")
    logger.info("Background tasks stopped")


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
    redoc_url="/redoc",
    lifespan=lifespan
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
    notifications_router,
    prefix="/notifications",
    tags=["notifications"],
    responses=create_error_responses()
)

# Кастомизация OpenAPI схемы для отображения X-API-Key в Swagger UI
def custom_openapi():
    """Добавляет X-API-Key в OpenAPI схему для Swagger UI"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Добавляем security scheme для X-API-Key
    openapi_schema["components"]["securitySchemes"] = {
        "X-API-Key": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API ключ для доступа к защищенным эндпоинтам"
        }
    }

    # Применяем security глобально ко всем эндпоинтам (кроме /, /health, /docs, /webhook/*)
    for path, path_item in openapi_schema["paths"].items():
        # Пропускаем эндпоинты, которые не требуют авторизации
        if path in ["/", "/health"] or path.startswith("/webhook/"):
            continue

        # Добавляем security ко всем методам в этом пути
        for method in path_item:
            if method in ["get", "post", "put", "patch", "delete"]:
                if "security" not in path_item[method]:
                    path_item[method]["security"] = [{"X-API-Key": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi



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
