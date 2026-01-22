"""API роуты для отчетов"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, status, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ReportResponse
from app.services import get_reports_by_user_id
from app.database import get_session
from app.utils.error_handler import handle_api_errors


router = APIRouter()


@router.get(
    "/user/{user_id}",
    response_model=List[ReportResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить все отчеты пользователя"
)
@handle_api_errors
async def get_reports_endpoint(
    user_id: UUID = Path(..., description="User UUID"),
    session: AsyncSession = Depends(get_session)
):
    """Получить все отчеты пользователя по user_id"""
    result = await get_reports_by_user_id(
        session=session,
        user_id=user_id
    )
    return result
