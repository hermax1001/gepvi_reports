"""Бизнес-логика для управления пользователями и подписками"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Webhook, WeightHistory
from app.schemas import (
    UserResponse, WebhookResponse, UpdateUserRequest
)
from app.utils.error_handler import NotFoundError

logger = logging.getLogger(__name__)


# User services
async def get_or_create_user(
    session: AsyncSession,
    telegram_user_id: str,
    timezone: str = "Europe/Moscow"
) -> UserResponse:
    """Получает или создает пользователя. По user_id только GET, по telegram_user_id GET or CREATE"""

    stmt = select(User).where(User.telegram_user_id == telegram_user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(telegram_user_id=telegram_user_id, timezone=timezone)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Created new user %s (telegram_user_id=%s, timezone=%s)", user.user_id, telegram_user_id, timezone)

    logger.info("Retrieved user %s (telegram_user_id=%s)", user.user_id, user.telegram_user_id)

    # Calculate has_active_subscription
    now = datetime.utcnow()
    has_active_subscription = (
        user.subscription_expires_at is not None and
        user.subscription_expires_at > now
    )

    return UserResponse(
        user_id=user.user_id,
        telegram_user_id=user.telegram_user_id,
        timezone=user.timezone,
        yob=user.yob,
        weight=user.weight,
        gender=user.gender,
        height=user.height,
        activity_level=user.activity_level,
        subscription_expires_at=user.subscription_expires_at,
        has_active_subscription=has_active_subscription,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


async def get_user_by_id(
    session: AsyncSession,
    user_id: UUID,
) -> UserResponse:
    """Получает пользователя по user_id (UUID)"""

    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(
            message=f"User not found for id={user_id}",
            details={'user_id': str(user_id)}
        )

    logger.info("Retrieved user %s (telegram_user_id=%s)", user.user_id, user.telegram_user_id)

    # Calculate has_active_subscription
    now = datetime.utcnow()
    has_active_subscription = (
        user.subscription_expires_at is not None and
        user.subscription_expires_at > now
    )

    return UserResponse(
        user_id=user.user_id,
        telegram_user_id=user.telegram_user_id,
        timezone=user.timezone,
        yob=user.yob,
        weight=user.weight,
        gender=user.gender,
        height=user.height,
        activity_level=user.activity_level,
        subscription_expires_at=user.subscription_expires_at,
        has_active_subscription=has_active_subscription,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


async def update_user(
    session: AsyncSession,
    user_id: UUID,
    update_data: UpdateUserRequest
) -> UserResponse:
    """Обновляет данные пользователя (PATCH - только переданные поля)"""

    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(
            message=f"User not found for id={user_id}",
            details={'user_id': str(user_id)}
        )

    # Сохраняем старый вес для проверки изменений
    old_weight = user.weight

    # Обновляем только переданные поля (PATCH behavior)
    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        setattr(user, field, value)

    # Обновляем timestamp
    user.updated_at = datetime.utcnow()

    # Если вес изменился - записываем в историю
    new_weight = user.weight
    if new_weight is not None and new_weight != old_weight:
        weight_history = WeightHistory(
            user_id=user.user_id,
            weight=new_weight
        )
        session.add(weight_history)
        logger.info("Added weight history for user %s: %.1f kg", user.user_id, new_weight)

    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info("Updated user %s (telegram_user_id=%s)", user.user_id, user.telegram_user_id)

    # Calculate has_active_subscription
    now = datetime.utcnow()
    has_active_subscription = (
        user.subscription_expires_at is not None and
        user.subscription_expires_at > now
    )

    return UserResponse(
        user_id=user.user_id,
        telegram_user_id=user.telegram_user_id,
        timezone=user.timezone,
        yob=user.yob,
        weight=user.weight,
        gender=user.gender,
        height=user.height,
        activity_level=user.activity_level,
        subscription_expires_at=user.subscription_expires_at,
        has_active_subscription=has_active_subscription,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


# Payment services
async def create_yookassa_payment(
    session: AsyncSession,
    user_id: UUID,
    package_type: str,
    return_url: str,
    telegram_user_id: Optional[str] = None
) -> dict:
    """Создает платеж в ЮKassa для подписки"""

    stmt = select(User).where(User.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError(
            message=f"User not found for id={user_id}",
            details={'user_id': user_id}
        )

    # Определяем сумму и описание в зависимости от пакета
    package_info = {
        "monthly": {
            "amount": 249.0,
            "description": "GepCalories Premium - 1 месяц безлимитного AI анализа еды",
        },
        "quarterly": {
            "amount": 599.0,
            "description": "GepCalories Premium - 3 месяца (скидка 20%, экономия 148₽)",
        },
        "yearly": {
            "amount": 1499.0,
            "description": "GepCalories Premium - 1 год (скидка 50%, экономия 1489₽)",
        }
    }

    if package_type not in package_info:
        raise NotFoundError(
            message=f"Unknown package type: {package_type}",
            details={'package_type': package_type}
        )

    package = package_info[package_type]

    try:
        # payment_info = await yookassa_client.create_payment(
        #     amount=package["amount"],
        #     description=package["description"],
        #     user_id=user.user_id,
        #     telegram_user_id=user.telegram_user_id,
        #     return_url=return_url
        # )

        logger.info("Created YooKassa payment %s for user %s (telegram_user_id=%s), package %s",
                   payment_info.get('id'), user.user_id, telegram_user_id, package_type)

        return payment_info

    except Exception as e:
        logger.error("Failed to create YooKassa payment for user %s: %s", user.user_id, e)
        raise NotFoundError(
            message=f"Failed to create payment: {str(e)}",
            details={'user_id': str(user_id), 'package_type': package_type}
        ) from e


async def process_yookassa_webhook(
    session: AsyncSession,
    provider_name: str,
    webhook_payload: dict
) -> WebhookResponse:
    """Обрабатывает входящий вебхук от ЮKassa и обновляет подписку"""
    # Сначала сохраняем вебхук в БД
    webhook = Webhook(
        provider_name=provider_name,
        webhook_payload=webhook_payload,
    )
    session.add(webhook)
    await session.commit()

    # Проверяем тип события
    event_type = webhook_payload.get("event")
    if event_type != "payment.succeeded":
        logger.info("Received non-successful YooKassa event: %s", event_type)
        webhook.response_code = 200
        await session.commit()
        return WebhookResponse(success=True)

    # Извлекаем данные платежа
    payment_object = webhook_payload.get("object", {})
    metadata = payment_object.get("metadata", {})

    user_id_str = metadata.get("user_id")
    telegram_user_id = metadata.get("telegram_user_id")

    # Нужен хотя бы один идентификатор
    if not user_id_str and not telegram_user_id:
        logger.warning("No user_id or telegram_user_id found in YooKassa payment metadata")
        webhook.response_code = 404
        await session.commit()
        raise NotFoundError(
            message="No user identification found in payment metadata",
            details={'metadata': metadata}
        )

    # Получаем сумму платежа для определения срока подписки
    amount = payment_object.get("amount", {}).get("value", "0")
    amount_rub = float(amount)

    # Определяем срок подписки на основе суммы
    # 249₽ = 1 месяц, 599₽ = 3 месяца, 1499₽ = 1 год
    if amount_rub >= 1499:
        months_to_add = 12
    elif amount_rub >= 599:
        months_to_add = 3
    else:
        months_to_add = 1

    # Получаем пользователя
    user = None

    # Приоритет - user_id (UUID)
    if user_id_str:
        try:
            uuid_id = UUID(user_id_str)
            user_stmt = select(User).where(User.user_id == uuid_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
        except (ValueError, AttributeError):
            logger.warning("Invalid user_id format in metadata: %s", user_id_str)

    # Если не нашли по UUID, пробуем по telegram_user_id
    if user is None and telegram_user_id:
        user_stmt = select(User).where(User.telegram_user_id == str(telegram_user_id))
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

    if user is None:
        logger.warning("User not found for payment metadata: user_id=%s, telegram_user_id=%s",
                      user_id_str, telegram_user_id)
        webhook.response_code = 404
        await session.commit()
        raise NotFoundError(
            message="User not found",
            details={'user_id': user_id_str, 'telegram_user_id': telegram_user_id}
        )

    # Обновляем подписку
    now = datetime.utcnow()

    # Если уже есть активная подписка, продлеваем от даты окончания
    if user.subscription_expires_at and user.subscription_expires_at > now:
        from dateutil.relativedelta import relativedelta
        user.subscription_expires_at = user.subscription_expires_at + relativedelta(months=months_to_add)
    else:
        # Иначе начинаем с текущей даты
        from dateutil.relativedelta import relativedelta
        user.subscription_expires_at = now + relativedelta(months=months_to_add)

    user.updated_at = now
    webhook.response_code = 200

    session.add(user)
    await session.commit()

    logger.info("Successfully processed YooKassa webhook for user %s (telegram_user_id=%s). Subscription until %s",
               user.user_id, user.telegram_user_id, user.subscription_expires_at)

    return WebhookResponse(success=True)
