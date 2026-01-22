"""Тесты для payments API и YooKassa webhooks"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Webhook
from settings.config import AppConfig


@pytest.mark.asyncio
async def test_create_payment_monthly(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест создания ежемесячного платежа"""
    # Создаем пользователя
    user = User(telegram_user_id="test_user_999")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    mock_payment_response = {
        "id": "test_payment_id_123",
        "status": "pending",
        "amount": {
            "value": "249.00",
            "currency": "RUB"
        },
        "description": "GepCalories Premium - 1 месяц безлимитного AI анализа еды",
        "confirmation": {
            "type": "redirect",
            "confirmation_url": "https://yookassa.ru/payments/test_payment_id_123"
        },
        "metadata": {
            "user_id": str(user.user_id),
            "telegram_user_id": "test_user_999"
        }
    }

    with patch('clients.yookassa.yookassa_client.create_payment', new=AsyncMock(return_value=mock_payment_response)):
        payment_request = {
            "user_id": str(user.user_id),
            "telegram_user_id": "test_user_999",
            "package_type": "monthly",
            "return_url": "https://t.me/gepcalories_bot"
        }

        response = await async_client.post(
            "/payments/create",
            json=payment_request,
            headers=api_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Проверяем структуру ответа
        assert data["payment_id"] == "test_payment_id_123"
        assert data["confirmation_url"] == "https://yookassa.ru/payments/test_payment_id_123"
        assert data["amount"] == 249.0
        assert "1 месяц" in data["description"]


@pytest.mark.asyncio
async def test_create_payment_invalid_package(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест создания платежа с неправильным типом пакета"""
    # Создаем пользователя
    user = User(telegram_user_id="test_user_999")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    payment_request = {
        "user_id": str(user.user_id),
        "telegram_user_id": "test_user_999",
        "package_type": "invalid_package",
        "return_url": "https://t.me/gepcalories_bot"
    }

    response = await async_client.post(
        "/payments/create",
        json=payment_request,
        headers=api_headers
    )

    assert response.status_code == 404
    data = response.json()
    assert "Unknown package type" in data["detail"]


@pytest.mark.asyncio
async def test_webhook_payment_succeeded_monthly(async_client: AsyncClient, session: AsyncSession):
    """Тест успешной обработки webhook от YooKassa для месячной подписки"""
    telegram_user_id = "webhook_user_123"

    # Создаем пользователя без подписки
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=None
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Подготавливаем webhook payload от YooKassa
    webhook_payload = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": "payment_id_123",
            "status": "succeeded",
            "amount": {
                "value": "249.00",
                "currency": "RUB"
            },
            "description": "GepCalories Premium - 1 месяц безлимитного AI анализа еды",
            "metadata": {
                "user_id": str(user.user_id),
                "telegram_user_id": telegram_user_id
            },
            "created_at": datetime.utcnow().isoformat(),
            "paid": True
        }
    }

    # Отправляем webhook (webhook endpoint не требует API key)
    response = await async_client.post(
        f"/webhook/{AppConfig.YOOKASSA_PROVIDER_ID}",
        json=webhook_payload
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}

    # Проверяем что webhook сохранился
    stmt = select(Webhook).where(Webhook.provider_name == AppConfig.YOOKASSA_PROVIDER_ID)
    result = await session.execute(stmt)
    webhook = result.scalar_one_or_none()

    assert webhook is not None
    assert webhook.response_code == 200
    assert webhook.webhook_payload == webhook_payload

    # Проверяем что подписка активирована (1 месяц)
    await session.refresh(user)
    assert user.subscription_expires_at is not None

    # Проверяем что срок подписки примерно через 1 месяц (± 1 день)
    expected_date = datetime.utcnow() + timedelta(days=30)
    days_diff = abs((user.subscription_expires_at - expected_date).days)
    assert days_diff <= 1  # Allow 1 day difference due to month variations


@pytest.mark.asyncio
async def test_webhook_payment_succeeded_yearly(async_client: AsyncClient, session: AsyncSession):
    """Тест успешной обработки webhook от YooKassa для годовой подписки"""
    telegram_user_id = "webhook_user_456"

    # Создаем пользователя без подписки
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=None
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Подготавливаем webhook payload для годовой подписки
    webhook_payload = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": "payment_id_456",
            "status": "succeeded",
            "amount": {
                "value": "1499.00",
                "currency": "RUB"
            },
            "description": "GepCalories Premium - 1 год (скидка 50%, экономия 1489₽)",
            "metadata": {
                "user_id": str(user.user_id),
                "telegram_user_id": telegram_user_id
            },
            "created_at": datetime.utcnow().isoformat(),
            "paid": True
        }
    }

    # Отправляем webhook
    response = await async_client.post(
        f"/webhook/{AppConfig.YOOKASSA_PROVIDER_ID}",
        json=webhook_payload
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}

    # Проверяем что подписка активирована (12 месяцев)
    await session.refresh(user)
    assert user.subscription_expires_at is not None

    # Проверяем что срок подписки примерно через 1 год (± 2 дня)
    expected_date = datetime.utcnow() + timedelta(days=365)
    days_diff = abs((user.subscription_expires_at - expected_date).days)
    assert days_diff <= 2  # Allow 2 days difference


@pytest.mark.asyncio
async def test_webhook_payment_extends_existing_subscription(async_client: AsyncClient, session: AsyncSession):
    """Тест продления существующей активной подписки"""
    telegram_user_id = "webhook_user_789"

    # Создаем пользователя с активной подпиской (еще 15 дней)
    existing_expiry = datetime.utcnow() + timedelta(days=15)
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=existing_expiry
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Оплачивает еще 1 месяц
    webhook_payload = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": "payment_id_789",
            "status": "succeeded",
            "amount": {
                "value": "249.00",
                "currency": "RUB"
            },
            "metadata": {
                "user_id": str(user.user_id),
                "telegram_user_id": telegram_user_id
            },
            "created_at": datetime.utcnow().isoformat(),
            "paid": True
        }
    }

    response = await async_client.post(
        f"/webhook/{AppConfig.YOOKASSA_PROVIDER_ID}",
        json=webhook_payload
    )

    assert response.status_code == 200

    # Проверяем что подписка продлена от старой даты
    await session.refresh(user)
    assert user.subscription_expires_at is not None

    # Подписка должна быть примерно через 15 дней + 1 месяц (± 2 дня)
    expected_date = existing_expiry + timedelta(days=30)
    days_diff = abs((user.subscription_expires_at - expected_date).days)
    assert days_diff <= 2


@pytest.mark.asyncio
async def test_webhook_user_not_found_error(async_client: AsyncClient, session: AsyncSession):
    """Тест что webhook возвращает 404 если пользователь не найден"""
    from uuid import uuid4

    fake_user_id = str(uuid4())

    # Отправляем webhook с несуществующим user_id
    webhook_payload = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": "payment_id_999",
            "status": "succeeded",
            "amount": {
                "value": "249.00",
                "currency": "RUB"
            },
            "metadata": {
                "user_id": fake_user_id
            },
            "created_at": datetime.utcnow().isoformat(),
            "paid": True
        }
    }

    response = await async_client.post(
        f"/webhook/{AppConfig.YOOKASSA_PROVIDER_ID}",
        json=webhook_payload
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_webhook_non_payment_event_ignored(async_client: AsyncClient, session: AsyncSession):
    """Тест что non-payment события игнорируются"""
    webhook_payload = {
        "type": "notification",
        "event": "payment.canceled",
        "object": {
            "id": "payment_id_canceled",
            "status": "canceled"
        }
    }

    response = await async_client.post(
        f"/webhook/{AppConfig.YOOKASSA_PROVIDER_ID}",
        json=webhook_payload
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}

    # Проверяем что webhook сохранен
    stmt = select(Webhook).where(Webhook.provider_name == AppConfig.YOOKASSA_PROVIDER_ID)
    result = await session.execute(stmt)
    webhook = result.scalar_one_or_none()
    assert webhook is not None
    assert webhook.response_code == 200
