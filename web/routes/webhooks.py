"""Публичные роуты для вебхуков (без API key проверки)"""
import logging

from fastapi import APIRouter, Request, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import WebhookResponse
from app.services import process_yookassa_webhook
from app.database import get_session
from app.utils.error_handler import handle_api_errors
from settings.config import AppConfig

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/webhook/{provider_id}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Обработка входящих вебхуков"
)
@handle_api_errors
async def webhook_handler(
    provider_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """Обрабатывает входящие вебхуки от внешних провайдеров"""

    # Проверяем что provider_id совпадает с настроенным
    if provider_id != AppConfig.YOOKASSA_PROVIDER_ID:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Получаем JSON payload
    webhook_payload = await request.json()

    # Обрабатываем вебхук
    result = await process_yookassa_webhook(
        session=session,
        provider_name=provider_id,
        webhook_payload=webhook_payload
    )

    return result
