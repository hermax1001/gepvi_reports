"""Универсальный обработчик ошибок для FastAPI"""
import logging
from typing import Optional, Dict, Any
from functools import wraps

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError as PydanticValidationError


logger = logging.getLogger(__name__)


class APIError(Exception):
    """Базовый класс для ошибок API"""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Ошибка валидации данных"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class ReportNoDataError(APIError):
    """Ошибка отсутсвия данных для репорта"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class NotFoundError(APIError):
    """Ошибка "не найдено" """
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, details=details)


def log_error(error: Exception, request: Optional[Request] = None, context: Optional[Dict[str, Any]] = None) -> None:
    """Логирует ошибку с контекстом"""
    context = context or {}

    # Добавляем информацию о запросе
    if request:
        context.update({
            'method': request.method,
            'url': str(request.url),
            'client_ip': request.client.host if request.client else None,
            'user_agent': request.headers.get('user-agent'),
        })

    # Определяем уровень логирования на основе типа ошибки
    if isinstance(error, APIError) or isinstance(error, HTTPException):
        if 400 <= error.status_code < 500:
            log_level = logging.WARNING
        else:
            log_level = logging.ERROR
    else:
        log_level = logging.ERROR

    # Формируем сообщение для лога
    log_message = f"API Error: {str(error)}"
    if context:
        log_message += f" | Context: {context}"

    # Логируем с соответствующим уровнем
    logger.log(log_level, log_message, exc_info=True)


def get_error_response(error: Exception) -> JSONResponse:
    """Возвращает JSON ответ с ошибкой"""
    if isinstance(error, APIError):
        status_code = error.status_code
        detail = error.message

        # Для ошибок 5xx скрываем детали от пользователя
        if status_code >= 500:
            detail = "Internal Server Error"
    else:
        status_code = 500
        detail = "Internal Server Error"

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "error_type": error.__class__.__name__ if isinstance(error, APIError) else "InternalError"
        }
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Глобальный обработчик исключений FastAPI"""
    # Логируем ошибку
    log_error(exc, request)

    # Возвращаем ответ
    return get_error_response(exc)


def handle_api_errors(func):
    """Декоратор для обработки ошибок в API endpoints"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except APIError as e:
            # Логируем APIError перед поднятием HTTPException
            log_error(e)
            message = e.message if e.status_code < 500 else "Internal Server Error"
            raise HTTPException(
                status_code=e.status_code,
                detail=message
            ) from e
        except HTTPException as e:
            log_error(e)
            raise
        except PydanticValidationError as e:
            # Ошибки валидации Pydantic
            log_error(e)
            raise HTTPException(
                status_code=400,
                detail=f"Validation error: {str(e)}"
            ) from e
        except ValueError as e:
            # Ошибки валидации значений
            log_error(e)
            raise HTTPException(
                status_code=400,
                detail=str(e)
            ) from e
        except SQLAlchemyError as e:
            # Ошибки базы данных
            log_error(e)
            raise HTTPException(
                status_code=500,
                detail="Database error occurred"
            ) from e
        except Exception as e:  # noqa: BLE001
            # Остальные ошибки
            log_error(e)
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error"
            ) from e

    return wrapper


def create_error_responses() -> Dict[int, Dict[str, Any]]:
    """Создает стандартные описания ошибок для OpenAPI"""
    return {
        400: {
            "description": "Bad Request",
            "content": {
                "application/json": {
                    "example": {"detail": "Validation error", "error_type": "ValidationError"}
                }
            }
        },
        404: {
            "description": "Not Found",
            "content": {
                "application/json": {
                    "example": {"detail": "Resource not found", "error_type": "NotFoundError"}
                }
            }
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {"detail": "Internal Server Error", "error_type": "InternalError"}
                }
            }
        }
    }
