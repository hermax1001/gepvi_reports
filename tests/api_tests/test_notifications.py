"""API тесты для уведомлений"""
import pytest
from uuid import uuid4


@pytest.mark.asyncio
async def test_get_notifications_by_user_id_empty(async_client, api_headers):
    """Тест получения уведомлений для пользователя без уведомлений"""
    user_id = uuid4()

    response = await async_client.get(
        f"/notifications/user/{user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_get_notifications_by_user_id_with_data(async_client, session, api_headers):
    """Тест получения уведомлений для пользователя с данными"""
    from app.models import Notification

    user_id = uuid4()

    # Создаем уведомление
    notification = Notification(
        user_id=user_id,
        text="Test notification",
        sender_method="telegram",
        meta={"chat_id": "123456"}
    )
    session.add(notification)
    await session.commit()

    # Запрашиваем уведомления
    response = await async_client.get(
        f"/notifications/user/{user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["user_id"] == str(user_id)
    assert data[0]["text"] == "Test notification"
    assert data[0]["sender_method"] == "telegram"
    assert data[0]["meta"] == {"chat_id": "123456"}
