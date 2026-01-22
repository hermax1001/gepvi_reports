"""API роуты для уведомлений"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, status, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import NotificationResponse
from app.services import get_notifications_by_user_id
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
