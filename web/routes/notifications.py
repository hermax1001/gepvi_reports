"""API роуты для уведомлений"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, status, Depends, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    NotificationResponse,
    NotificationReserveRequest,
    NotificationSuccessRequest
)
from app.services import (
    get_notifications_by_user_id,
    reserve_notifications,
    mark_notifications_success
)
from app.database import get_session
from app.utils.error_handler import handle_api_errors


router = APIRouter()


@router.get(
    "/user/{user_id}",
    response_model=List[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить все уведомления пользователя"
)
@handle_api_errors
async def get_notifications_endpoint(
    user_id: UUID = Path(..., description="User UUID"),
    session: AsyncSession = Depends(get_session)
):
    """Получить все уведомления пользователя по user_id"""
    result = await get_notifications_by_user_id(
        session=session,
        user_id=user_id
    )
    return result


@router.post(
    "/reserve",
    response_model=List[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Зарезервировать новые уведомления для отправки"
)
@handle_api_errors
async def reserve_notifications_endpoint(
    request: NotificationReserveRequest = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """Резервирует новые уведомления (переводит в in_progress) и возвращает их"""
    result = await reserve_notifications(
        session=session,
        sender_method=request.sender_method,
        limit=request.limit
    )
    return result


@router.post(
    "/success",
    status_code=status.HTTP_200_OK,
    summary="Отметить уведомления как успешно отправленные или failed"
)
@handle_api_errors
async def mark_success_endpoint(
    request: NotificationSuccessRequest = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """Переводит уведомления в статус success или failed"""
    result = await mark_notifications_success(
        session=session,
        notification_ids=request.notification_ids,
        failed_ids=request.failed_ids
    )
    return result
