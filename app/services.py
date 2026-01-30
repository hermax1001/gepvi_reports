"""Бизнес-логика для управления отчетами, задачами и уведомлениями"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any
from uuid import UUID

import httpx
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, Notification
from app.schemas import ReportResponse, NotificationResponse
from app.utils.error_handler import ValidationError, ReportNoDataError
from clients.gepvi_eat_client import gepvi_eat_client
from clients.gepvi_users_client import gepvi_users_client
from clients.open_router import open_router_client
from settings.config import AppConfig

logger = logging.getLogger(__name__)


# Report services
async def get_report_data(
    user_id: UUID,
    start_date: datetime,
    end_date: datetime,
    period: str
) -> Tuple[Dict[Any, Any], str, datetime, datetime]:
    """
    Получает данные для отчета с умной валидацией и автокорректировкой периода.

    Returns:
        Tuple of (report_data, adjusted_period, adjusted_start_date, adjusted_end_date)
    """
    # Получаем данные от gepvi_eat
    report_data = await gepvi_eat_client.get_user_report_data(user_id, start_date, end_date)
    if not report_data or not report_data.get("meal_components_by_day"):
        raise ReportNoDataError("Insufficient data for report. No meals found in this period.")

    # Логика валидации и перезапроса
    if period == "month" and len(report_data.get("meal_components_by_day", [])) < 10:

        # Пробуем недельный: последние 7 дней от end_date назад
        new_start_date = end_date - timedelta(days=7)  # 7 дней включая end_date
        logger.info("Retrying with weekly period: %s to %s", new_start_date.isoformat(), end_date.isoformat())
        period = "week"

        # Получаем данные от gepvi_eat
        report_data = await gepvi_eat_client.get_user_report_data(user_id, start_date, end_date)
        if not report_data or not report_data.get("meal_components_by_day"):
            raise ReportNoDataError("Insufficient data for report. No meals found in this period.")


    if period == "week" and len(report_data.get("meal_components_by_day", [])) < 3:
        new_start_date = end_date - timedelta(days=1)  # 7 дней включая end_date
        logger.info("Retrying with weekly period: %s to %s", new_start_date.isoformat(), end_date.isoformat())
        period = "day"

        # Получаем данные от gepvi_eat
        report_data = await gepvi_eat_client.get_user_report_data(user_id, start_date, end_date)
        if not report_data or not report_data.get("meal_components_by_day"):
            raise ReportNoDataError("Insufficient data for report. No meals found in this period.")

    if period == "day" and len(report_data.get("meal_components_by_day", [])) < 1:
        raise ReportNoDataError("Insufficient data for report. No meals found in this period.")

    # Данных достаточно для запрошенного периода
    return report_data, period, start_date, end_date


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
            created_at=report.created_at,
            updated_at=report.updated_at
        )
        for report in reports
    ]


async def create_report_with_notification(
    session: AsyncSession,
    user_id: UUID,
    start_date: datetime,
    end_date: datetime,
    period: str,
    sender_method: str
) -> ReportResponse:
    """Creates AI-generated report and notification"""
    # Validate period
    if period not in ("day", "week", "month"):
        raise ValidationError(f"Invalid period: {period}. Must be day, week, or month")

    original_period = period

    # Get report data with smart validation and period adjustment
    report_data, adjusted_period, adjusted_start_date, adjusted_end_date = await get_report_data(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        period=period
    )

    # Extract data
    user_goals = report_data.get("user_macros_goals", {})
    summary = report_data.get("summary", {})
    daily_components = report_data.get("meal_components_by_day", [])
    days_count = len(daily_components)

    if original_period != adjusted_period:
        logger.info("Period adjusted from %s to %s based on available data (%d days)", original_period, adjusted_period, days_count)

    # Get user info for personalized report
    user_info = {}
    try:
        user_data = await gepvi_users_client.get_user_by_user_id(user_id)
        user_info = {
            "yob": user_data.get("yob"),
            "weight": user_data.get("weight"),
            "gender": user_data.get("gender"),
            "height": user_data.get("height"),
            "activity_level": user_data.get("activity_level")
        }
        logger.debug("Retrieved user info for report: %s", user_info)
    except Exception as e:
        logger.warning("Could not retrieve user info for report: %s", e)
        # Continue without user info - report will note that profile is not filled

    # Generate AI report
    try:
        report_text = await open_router_client.generate_report(
            period=adjusted_period,
            start_date=adjusted_start_date,
            end_date=adjusted_end_date,
            user_goals=user_goals,
            summary=summary,
            daily_components=daily_components,
            user_info=user_info
        )
    except Exception as e:
        logger.error("Failed to generate AI report: %s", e)
        raise ValidationError(f"Could not generate AI report: {e}")

    # Save report to database
    report = Report(
        user_id=user_id,
        report_type=adjusted_period,
        result=report_text
    )
    session.add(report)
    await session.flush()

    # Create notification
    notification = Notification(
        user_id=user_id,
        text=None,  # Will use report.result when reserved
        sender_method=sender_method,
        report_id=report.id,
        meta={
            "period": adjusted_period,
            "start_date": adjusted_start_date.isoformat(),
            "end_date": adjusted_end_date.isoformat(),
            "original_period": original_period,
            "days_count": days_count,
        }
    )
    session.add(notification)
    await session.commit()

    logger.info("Created report id=%s and notification for user %s", report.id, user_id)

    return ReportResponse(
        id=report.id,
        user_id=report.user_id,
        report_type=report.report_type,
        result=report.result,
        created_at=report.created_at,
        updated_at=report.updated_at
    )


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
        .order_by(Notification.created_at)
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
    notification_ids: List[int],
    failed_ids: List[int] = None
) -> dict:
    """Переводит уведомления в статус success или failed"""
    success_count = 0
    failed_count = 0

    # Обрабатываем успешные уведомления
    if notification_ids:
        success_stmt = (
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(
                status="success",
                updated_at=datetime.now(timezone.utc)
            )
        )
        result = await session.execute(success_stmt)
        success_count = result.rowcount
        logger.info("Marked %d notifications as success", success_count)

    # Обрабатываем failed уведомления
    if failed_ids:
        failed_stmt = (
            update(Notification)
            .where(Notification.id.in_(failed_ids))
            .values(
                status="failed",
                updated_at=datetime.now(timezone.utc)
            )
        )
        result = await session.execute(failed_stmt)
        failed_count = result.rowcount
        logger.info("Marked %d notifications as failed", failed_count)

    await session.commit()

    return {
        "success_count": success_count,
        "failed_count": failed_count
    }


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
