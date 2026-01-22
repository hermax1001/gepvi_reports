"""Бизнес-логика для управления отчетами, задачами и уведомлениями"""
import logging
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, Task, Notification
from app.schemas import ReportResponse, TaskResponse, NotificationResponse

logger = logging.getLogger(__name__)


# Report services
async def get_reports_by_user_id(
    session: AsyncSession,
    user_id: UUID
) -> List[ReportResponse]:
    """Получает все отчеты пользователя по user_id"""
    stmt = select(Report).where(Report.user_id == user_id)
    result = await session.execute(stmt)
    reports = result.scalars().all()

    logger.info("Retrieved %d reports for user %s", len(reports), user_id)

    return [
        ReportResponse(
            id=report.id,
            user_id=report.user_id,
            report_type=report.report_type,
            result=report.result,
            task_id=report.task_id,
            created_at=report.created_at,
            updated_at=report.updated_at
        )
        for report in reports
    ]


# Task services
async def get_tasks_by_user_id(
    session: AsyncSession,
    user_id: UUID
) -> List[TaskResponse]:
    """Получает все задачи пользователя по user_id"""
    stmt = select(Task).where(Task.user_id == user_id)
    result = await session.execute(stmt)
    tasks = result.scalars().all()

    logger.info("Retrieved %d tasks for user %s", len(tasks), user_id)

    return [
        TaskResponse(
            id=task.id,
            user_id=task.user_id,
            next_task_time=task.next_task_time,
            period=task.period,
            created_at=task.created_at,
            updated_at=task.updated_at
        )
        for task in tasks
    ]


# Notification services
async def get_notifications_by_user_id(
    session: AsyncSession,
    user_id: UUID
) -> List[NotificationResponse]:
    """Получает все уведомления пользователя по user_id"""
    stmt = select(Notification).where(Notification.user_id == user_id)
    result = await session.execute(stmt)
    notifications = result.scalars().all()

    logger.info("Retrieved %d notifications for user %s", len(notifications), user_id)

    return [
        NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            text=notification.text,
            sender_method=notification.sender_method,
            meta=notification.meta,
            created_at=notification.created_at,
            updated_at=notification.updated_at
        )
        for notification in notifications
    ]
