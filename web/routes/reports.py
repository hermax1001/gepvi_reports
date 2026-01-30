"""API роуты для отчетов"""
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, status, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ReportResponse
from app.services import get_reports_by_user_id, create_report_with_notification
from app.database import get_session
from app.utils.error_handler import handle_api_errors


router = APIRouter()


class GenerateReportRequest(BaseModel):
    """Request to generate a report"""
    start_date: datetime
    end_date: datetime
    period: str = Field(..., pattern="^(day|week|month)$")
    sender_method: str


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


@router.post(
    "/generate/{user_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Генерировать AI отчет для пользователя"
)
@handle_api_errors
async def generate_report_endpoint(
    user_id: UUID = Path(..., description="User UUID"),
    request: GenerateReportRequest = ...,
    session: AsyncSession = Depends(get_session)
):
    """Генерирует AI отчет, создает уведомление"""
    result = await create_report_with_notification(
        session=session,
        user_id=user_id,
        start_date=request.start_date,
        end_date=request.end_date,
        period=request.period,
        sender_method=request.sender_method
    )
    return result
