"""Тесты для users API"""
import pytest
from datetime import datetime, timedelta
from uuid import UUID
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User


@pytest.mark.asyncio
async def test_get_or_create_user_new_by_telegram_id(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест создания нового пользователя по telegram_user_id"""
    telegram_user_id = "test_user_123"

    response = await async_client.post(
        "/users/get_or_create",
        json={"telegram_user_id": telegram_user_id},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем структуру ответа
    assert "user_id" in data
    assert UUID(data["user_id"])  # Проверяем что это валидный UUID
    assert data["telegram_user_id"] == telegram_user_id
    assert data["subscription_expires_at"] is None
    assert data["has_active_subscription"] is False
    assert "created_at" in data
    assert "updated_at" in data

    # Проверяем что пользователь сохранился в БД
    user_uuid = UUID(data["user_id"])
    stmt = select(User).where(User.user_id == user_uuid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.user_id == user_uuid
    assert user.telegram_user_id == telegram_user_id


@pytest.mark.asyncio
async def test_get_or_create_user_existing_by_telegram_id(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест получения существующего пользователя по telegram_user_id"""
    telegram_user_id = "existing_user_456"

    # Создаем пользователя напрямую в БД
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=None
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Запрашиваем существующего пользователя
    response = await async_client.post(
        "/users/get_or_create",
        json={"telegram_user_id": telegram_user_id},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что вернулись существующие данные
    assert UUID(data["user_id"]) == user.user_id
    assert data["telegram_user_id"] == telegram_user_id
    assert data["subscription_expires_at"] is None
    assert data["has_active_subscription"] is False


@pytest.mark.asyncio
async def test_get_or_create_user_existing_by_uuid(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест получения существующего пользователя по UUID"""
    telegram_user_id = "uuid_test_user"

    # Создаем пользователя напрямую в БД
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=None
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Запрашиваем существующего пользователя по UUID
    response = await async_client.post(
        "/users/get_or_create",
        json={"telegram_user_id": telegram_user_id},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что вернулись существующие данные
    assert UUID(data["user_id"]) == user.user_id
    assert data["telegram_user_id"] == telegram_user_id
    assert data["subscription_expires_at"] is None
    assert data["has_active_subscription"] is False


@pytest.mark.asyncio
async def test_get_or_create_user_with_active_subscription(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест получения пользователя с активной подпиской"""
    telegram_user_id = "user_with_subscription"

    # Создаем пользователя с активной подпиской
    future_date = datetime.utcnow() + timedelta(days=30)
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=future_date
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    response = await async_client.post(
        "/users/get_or_create",
        json={"telegram_user_id": telegram_user_id},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем статус подписки
    assert UUID(data["user_id"]) == user.user_id
    assert data["telegram_user_id"] == telegram_user_id
    assert data["has_active_subscription"] is True
    assert data["subscription_expires_at"] is not None


@pytest.mark.asyncio
async def test_get_or_create_user_with_expired_subscription(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест получения пользователя с истекшей подпиской"""
    telegram_user_id = "user_expired_sub"

    # Создаем пользователя с истекшей подпиской
    past_date = datetime.utcnow() - timedelta(days=5)
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=past_date
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    response = await async_client.post(
        "/users/get_or_create",
        json={"telegram_user_id": telegram_user_id},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что подписка неактивна
    assert UUID(data["user_id"]) == user.user_id
    assert data["telegram_user_id"] == telegram_user_id
    assert data["has_active_subscription"] is False
    assert data["subscription_expires_at"] is not None


@pytest.mark.asyncio
async def test_get_or_create_user_without_identifiers(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что запрос без идентификаторов возвращает ошибку"""
    response = await async_client.post(
        "/users/get_or_create",
        json={},
        headers=api_headers
    )

    assert response.status_code >= 400 < 500
    data = response.json()
    assert "Field required" in data["detail"][0]['msg']


@pytest.mark.asyncio
async def test_get_user_by_id_existing(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест получения существующего пользователя по user_id"""
    telegram_user_id = "get_by_id_test"

    # Создаем пользователя напрямую в БД
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=None
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Запрашиваем пользователя по UUID через GET эндпоинт
    response = await async_client.get(
        f"/users/{user.user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем структуру ответа
    assert UUID(data["user_id"]) == user.user_id
    assert data["telegram_user_id"] == telegram_user_id
    assert data["subscription_expires_at"] is None
    assert data["has_active_subscription"] is False
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_user_by_id_with_active_subscription(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест получения пользователя с активной подпиской по user_id"""
    telegram_user_id = "get_by_id_active_sub"

    # Создаем пользователя с активной подпиской
    future_date = datetime.utcnow() + timedelta(days=30)
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=future_date
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    response = await async_client.get(
        f"/users/{user.user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем статус подписки
    assert UUID(data["user_id"]) == user.user_id
    assert data["telegram_user_id"] == telegram_user_id
    assert data["has_active_subscription"] is True
    assert data["subscription_expires_at"] is not None


@pytest.mark.asyncio
async def test_get_user_by_id_with_expired_subscription(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест получения пользователя с истекшей подпиской по user_id"""
    telegram_user_id = "get_by_id_expired_sub"

    # Создаем пользователя с истекшей подпиской
    past_date = datetime.utcnow() - timedelta(days=5)
    user = User(
        telegram_user_id=telegram_user_id,
        subscription_expires_at=past_date
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    response = await async_client.get(
        f"/users/{user.user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что подписка неактивна
    assert UUID(data["user_id"]) == user.user_id
    assert data["telegram_user_id"] == telegram_user_id
    assert data["has_active_subscription"] is False
    assert data["subscription_expires_at"] is not None


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что запрос несуществующего пользователя возвращает 404"""
    from uuid import uuid4

    non_existent_id = uuid4()

    response = await async_client.get(
        f"/users/{non_existent_id}",
        headers=api_headers
    )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in str(data)


@pytest.mark.asyncio
async def test_get_user_by_id_invalid_uuid(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что запрос с невалидным UUID возвращает ошибку"""

    response = await async_client.get(
        "/users/invalid-uuid-string",
        headers=api_headers
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_or_create_user_default_timezone(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест создания пользователя с дефолтной таймзоной Europe/Moscow"""
    telegram_user_id = "test_default_timezone"

    response = await async_client.post(
        "/users/get_or_create",
        json={"telegram_user_id": telegram_user_id},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что таймзона по умолчанию Europe/Moscow
    assert data["timezone"] == "Europe/Moscow"
    assert "user_id" in data

    # Проверяем что в БД сохранилось правильное значение
    user_uuid = UUID(data["user_id"])
    stmt = select(User).where(User.user_id == user_uuid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.timezone == "Europe/Moscow"


@pytest.mark.asyncio
async def test_get_or_create_user_custom_timezone(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест создания пользователя с кастомной таймзоной"""
    telegram_user_id = "test_custom_timezone"
    custom_timezone = "America/New_York"

    response = await async_client.post(
        "/users/get_or_create",
        json={
            "telegram_user_id": telegram_user_id,
            "timezone": custom_timezone
        },
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что таймзона установлена правильно
    assert data["timezone"] == custom_timezone
    assert "user_id" in data

    # Проверяем что в БД сохранилось правильное значение
    user_uuid = UUID(data["user_id"])
    stmt = select(User).where(User.user_id == user_uuid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    assert user is not None
    assert user.timezone == custom_timezone


@pytest.mark.asyncio
async def test_get_user_by_id_returns_timezone(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что GET /users/{user_id} возвращает таймзону"""
    telegram_user_id = "test_get_timezone"
    custom_timezone = "Asia/Tokyo"

    # Создаем пользователя с кастомной таймзоной
    user = User(
        telegram_user_id=telegram_user_id,
        timezone=custom_timezone,
        subscription_expires_at=None
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Запрашиваем пользователя по UUID
    response = await async_client.get(
        f"/users/{user.user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что таймзона вернулась правильно
    assert data["timezone"] == custom_timezone
    assert UUID(data["user_id"]) == user.user_id


@pytest.mark.asyncio
async def test_get_or_create_existing_user_preserves_timezone(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что при повторном запросе существующего пользователя таймзона сохраняется"""
    telegram_user_id = "test_preserve_timezone"
    original_timezone = "Europe/London"

    # Создаем пользователя с определенной таймзоной
    user = User(
        telegram_user_id=telegram_user_id,
        timezone=original_timezone,
        subscription_expires_at=None
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Запрашиваем существующего пользователя с другой таймзоной в запросе
    response = await async_client.post(
        "/users/get_or_create",
        json={
            "telegram_user_id": telegram_user_id,
            "timezone": "America/Chicago"  # Другая таймзона
        },
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что таймзона осталась оригинальной (не перезаписалась)
    assert data["timezone"] == original_timezone
    assert UUID(data["user_id"]) == user.user_id


# PATCH /users/{user_id} tests

@pytest.mark.asyncio
async def test_update_user_single_field(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест обновления одного поля через PATCH"""
    telegram_user_id = "test_update_single"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id, timezone="Europe/Moscow")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Обновляем только timezone
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"timezone": "America/New_York"},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что timezone обновился
    assert data["timezone"] == "America/New_York"
    assert UUID(data["user_id"]) == user.user_id
    # Остальные поля остались None
    assert data["yob"] is None
    assert data["weight"] is None
    assert data["gender"] is None
    assert data["height"] is None
    assert data["activity_level"] is None


@pytest.mark.asyncio
async def test_update_user_multiple_fields(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест обновления нескольких полей одновременно"""
    telegram_user_id = "test_update_multiple"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Обновляем несколько полей
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={
            "yob": 1990,
            "weight": 75.5,
            "gender": "m",
            "height": 180,
            "activity_level": 1.75
        },
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что все поля обновились
    assert data["yob"] == 1990
    assert data["weight"] == 75.5
    assert data["gender"] == "m"
    assert data["height"] == 180
    assert data["activity_level"] == 1.75
    assert UUID(data["user_id"]) == user.user_id


@pytest.mark.asyncio
async def test_update_user_weight_creates_history(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что обновление веса создает запись в weight_history"""
    from app.models import WeightHistory
    telegram_user_id = "test_weight_history"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Обновляем вес первый раз
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"weight": 80.0},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["weight"] == 80.0

    # Проверяем что запись появилась в weight_history
    stmt = select(WeightHistory).where(WeightHistory.user_id == user.user_id)
    result = await session.execute(stmt)
    history = result.scalars().all()

    assert len(history) == 1
    assert history[0].weight == 80.0
    assert history[0].user_id == user.user_id


@pytest.mark.asyncio
async def test_update_user_weight_multiple_times(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что повторное обновление веса создает новую запись в weight_history"""
    from app.models import WeightHistory
    telegram_user_id = "test_weight_multiple"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Первое обновление веса
    await async_client.patch(
        f"/users/{user.user_id}",
        json={"weight": 80.0},
        headers=api_headers
    )

    # Второе обновление веса
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"weight": 78.5},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["weight"] == 78.5

    # Проверяем что в weight_history 2 записи
    stmt = select(WeightHistory).where(WeightHistory.user_id == user.user_id).order_by(WeightHistory.created_at)
    result = await session.execute(stmt)
    history = result.scalars().all()

    assert len(history) == 2
    assert history[0].weight == 80.0
    assert history[1].weight == 78.5


@pytest.mark.asyncio
async def test_update_user_weight_same_value_no_history(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что обновление веса на то же значение не создает новую запись"""
    from app.models import WeightHistory
    telegram_user_id = "test_weight_same"

    # Создаем пользователя с весом
    user = User(telegram_user_id=telegram_user_id, weight=80.0)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Обновляем другие поля, вес не меняем
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"height": 180},
        headers=api_headers
    )

    assert response.status_code == 200

    # Проверяем что в weight_history нет записей
    stmt = select(WeightHistory).where(WeightHistory.user_id == user.user_id)
    result = await session.execute(stmt)
    history = result.scalars().all()

    assert len(history) == 0


@pytest.mark.asyncio
async def test_update_user_invalid_gender(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест валидации gender - только m или f"""
    telegram_user_id = "test_invalid_gender"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Пытаемся установить невалидный gender
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"gender": "x"},
        headers=api_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_user_invalid_yob_future(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест валидации yob - не может быть больше текущего года"""
    telegram_user_id = "test_invalid_yob"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Пытаемся установить год рождения в будущем
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"yob": 2050},
        headers=api_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_user_invalid_yob_too_old(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест валидации yob - не может быть меньше 1900"""
    telegram_user_id = "test_yob_too_old"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Пытаемся установить год рождения меньше 1900
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"yob": 1899},
        headers=api_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_user_invalid_weight_too_low(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест валидации weight - не может быть меньше 20"""
    telegram_user_id = "test_weight_too_low"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Пытаемся установить вес меньше 20
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"weight": 15.0},
        headers=api_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_user_invalid_weight_too_high(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест валидации weight - не может быть больше 500"""
    telegram_user_id = "test_weight_too_high"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Пытаемся установить вес больше 500
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"weight": 600.0},
        headers=api_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_user_invalid_height_too_low(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест валидации height - не может быть меньше 70"""
    telegram_user_id = "test_height_too_low"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Пытаемся установить рост меньше 70
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"height": 50},
        headers=api_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_user_invalid_height_too_high(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест валидации height - не может быть больше 290"""
    telegram_user_id = "test_height_too_high"

    # Создаем пользователя
    user = User(telegram_user_id=telegram_user_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Пытаемся установить рост больше 290
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"height": 300},
        headers=api_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_user_not_found(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что PATCH для несуществующего пользователя возвращает 404"""
    from uuid import uuid4

    non_existent_id = uuid4()

    response = await async_client.patch(
        f"/users/{non_existent_id}",
        json={"timezone": "UTC"},
        headers=api_headers
    )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in str(data)


@pytest.mark.asyncio
async def test_update_user_preserves_unmodified_fields(async_client: AsyncClient, api_headers: dict, session: AsyncSession):
    """Тест что PATCH не меняет поля которые не переданы в запросе"""
    telegram_user_id = "test_preserve_fields"

    # Создаем пользователя со всеми заполненными полями
    user = User(
        telegram_user_id=telegram_user_id,
        timezone="Europe/London",
        yob=1985,
        weight=70.0,
        gender="f",
        height=165,
        activity_level=2.50
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Обновляем только timezone
    response = await async_client.patch(
        f"/users/{user.user_id}",
        json={"timezone": "Asia/Tokyo"},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем что timezone обновился, а остальные поля остались
    assert data["timezone"] == "Asia/Tokyo"
    assert data["yob"] == 1985
    assert data["weight"] == 70.0
    assert data["gender"] == "f"
    assert data["height"] == 165
    assert data["activity_level"] == 2.50
