"""Pydantic схемы для API"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field as PydanticField


# Report schemas
class ReportResponse(BaseModel):
    """Ответ с данными отчета"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    report_type: str
    result: str
    task_id: int
    created_at: datetime
    updated_at: datetime


# Task schemas
class TaskResponse(BaseModel):
    """Ответ с данными задачи"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    next_task_time: datetime
    period: str
    created_at: datetime
    updated_at: datetime


# Notification schemas
class NotificationResponse(BaseModel):
    """Ответ с данными уведомления"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    text: Optional[str]
    sender_method: str
    meta: dict
    status: str
    retry_count: int
    report_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class NotificationReserveRequest(BaseModel):
    """Запрос на резервацию уведомлений"""
    sender_method: str
    limit: int = PydanticField(default=100, ge=1, le=100)


class NotificationSuccessRequest(BaseModel):
    """Запрос на пометку уведомлений как успешных"""
    notification_ids: list[int]
