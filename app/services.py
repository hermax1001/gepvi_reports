"""Бизнес-логика для управления отчетами, задачами и уведомлениями"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List
from uuid import UUID

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, Task, Notification
from app.schemas import ReportResponse, TaskResponse, NotificationResponse
from settings.config import AppConfig

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
            status=notification.status,
            retry_count=notification.retry_count,
            report_id=notification.report_id,
            created_at=notification.created_at,
            updated_at=notification.updated_at
        )
        for notification in notifications
    ]


async def reserve_notifications(
    session: AsyncSession,
    sender_method: str,
    limit: int = 100
) -> List[NotificationResponse]:
    """Резервирует новые уведомления (переводит в in_progress) и возвращает их"""
    # Ограничиваем limit от 1 до 100
    limit = max(1, min(limit, 100))

    # Атомарная операция: SELECT + UPDATE с RETURNING
    # Используем подзапрос для получения ID нужных записей
    subquery = (
        select(Notification.id)
        .where(
            and_(
                Notification.status == "new",
                Notification.sender_method == sender_method
            )
        )
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    # UPDATE с RETURNING всех данных
    stmt = (
        update(Notification)
        .where(Notification.id.in_(subquery))
        .values(
            status="in_progress",
            updated_at=datetime.now(timezone.utc)
        )
        .returning(Notification)
    )

    result = await session.execute(stmt)
    await session.commit()
    notifications = result.scalars().all()

    if not notifications:
        logger.info("No new notifications found for sender_method=%s", sender_method)
        return []

    # Собираем report_ids для загрузки reports одним запросом
    report_ids = [n.report_id for n in notifications if n.report_id is not None]

    # Загружаем reports если есть
    reports_map = {}
    if report_ids:
        reports_stmt = select(Report).where(Report.id.in_(report_ids))
        reports_result = await session.execute(reports_stmt)
        reports = reports_result.scalars().all()
        reports_map = {report.id: report.result for report in reports}

    logger.info("Reserved %d notifications for sender_method=%s", len(notifications), sender_method)

    # Формируем ответ, подставляя текст из report если нужно
    return [
        NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            text=reports_map.get(notification.report_id) if notification.report_id else notification.text,
            sender_method=notification.sender_method,
            meta=notification.meta,
            status=notification.status,
            retry_count=notification.retry_count,
            report_id=notification.report_id,
            created_at=notification.created_at,
            updated_at=notification.updated_at
        )
        for notification in notifications
    ]


async def mark_notifications_success(
    session: AsyncSession,
    notification_ids: List[int]
) -> int:
    """Переводит уведомления в статус success"""
    stmt = (
        update(Notification)
        .where(Notification.id.in_(notification_ids))
        .values(
            status="success",
            updated_at=datetime.now(timezone.utc)
        )
    )

    result = await session.execute(stmt)
    await session.commit()

    logger.info("Marked %d notifications as success", result.rowcount)

    return result.rowcount


async def process_stuck_notifications(session: AsyncSession) -> None:
    """Background job: обрабатывает провисевшие уведомления в статусе in_progress"""
    timeout_minutes = AppConfig.NOTIFICATION_RETRY_TIMEOUT_MINUTES
    max_retry_count = AppConfig.NOTIFICATION_MAX_RETRY_COUNT

    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    # Получаем только ID и retry_count провисевших уведомлений (экономия памяти)
    stmt = select(Notification.id, Notification.retry_count).where(
        and_(
            Notification.status == "in_progress",
            Notification.updated_at < timeout_threshold
        )
    )

    result = await session.execute(stmt)
    stuck_notifications = result.all()

    if not stuck_notifications:
        logger.debug("No stuck notifications found")
        return

    # Разделяем на те, которые нужно повторить и те, которые failed
    to_retry = []
    to_error = []

    for notification_id, retry_count in stuck_notifications:
        if retry_count < max_retry_count:
            to_retry.append(notification_id)
        else:
            to_error.append(notification_id)

    # Обновляем статусы батчами
    if to_retry:
        retry_stmt = (
            update(Notification)
            .where(Notification.id.in_(to_retry))
            .values(
                status="new",
                retry_count=Notification.retry_count + 1,
                updated_at=datetime.now(timezone.utc)
            )
        )
        await session.execute(retry_stmt)
        logger.info("Retrying %d notifications", len(to_retry))

    if to_error:
        error_stmt = (
            update(Notification)
            .where(Notification.id.in_(to_error))
            .values(
                status="error",
                updated_at=datetime.now(timezone.utc)
            )
        )
        await session.execute(error_stmt)
        logger.info("Marked %d notifications as error", len(to_error))

    await session.commit()
    logger.info("Processed %d stuck notifications", len(stuck_notifications))
