"""API роуты для пользователей"""
from uuid import UUID
from fastapi import APIRouter, status, Depends, Body, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import UserResponse, GetOrCreateUserRequest, UpdateUserRequest
from app.services import get_or_create_user, get_user_by_id, update_user
from app.database import get_session
from app.utils.error_handler import handle_api_errors


router = APIRouter()


@router.post(
    "/get_or_create",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить или создать пользователя"
)
@handle_api_errors
async def get_or_create_user_endpoint(
    request: GetOrCreateUserRequest = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """Получить или создать пользователя по user_id (UUID) или telegram_user_id"""
    result = await get_or_create_user(
        session=session,
        telegram_user_id=request.telegram_user_id,
        timezone=request.timezone
    )
    return result


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить пользователя по user_id"
)
@handle_api_errors
async def get_user_endpoint(
    user_id: UUID = Path(..., description="User UUID"),
    session: AsyncSession = Depends(get_session)
):
    """Получить пользователя по user_id (UUID)"""
    result = await get_user_by_id(
        session=session,
        user_id=user_id
    )
    return result


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить данные пользователя"
)
@handle_api_errors
async def update_user_endpoint(
    user_id: UUID = Path(..., description="User UUID"),
    request: UpdateUserRequest = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """Обновить данные пользователя (timezone, yob, weight, gender, height, activity_level)"""
    result = await update_user(
        session=session,
        user_id=user_id,
        update_data=request
    )
    return result
