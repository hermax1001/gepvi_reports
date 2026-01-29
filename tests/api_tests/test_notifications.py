"""API тесты для уведомлений"""
import pytest
from datetime import datetime, timezone, timedelta
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
    assert data[0]["status"] == "new"
    assert data[0]["retry_count"] == 0
    assert data[0]["report_id"] is None


@pytest.mark.asyncio
async def test_reserve_notifications_without_report(async_client, session, api_headers):
    """Тест резервации уведомлений без report_id"""
    from app.models import Notification

    user_id = uuid4()

    # Создаем уведомления
    notification1 = Notification(
        user_id=user_id,
        text="Test notification 1",
        sender_method="gepvi_eat_bot",
        meta={"chat_id": "123456"}
    )
    notification2 = Notification(
        user_id=user_id,
        text="Test notification 2",
        sender_method="gepvi_eat_bot",
        meta={"chat_id": "123456"}
    )
    notification3 = Notification(
        user_id=user_id,
        text="Test notification 3",
        sender_method="email",  # Другой sender_method
        meta={}
    )
    session.add_all([notification1, notification2, notification3])
    await session.commit()

    # Резервируем уведомления для gepvi_eat_bot
    response = await async_client.post(
        "/notifications/reserve",
        json={"sender_method": "gepvi_eat_bot", "limit": 100},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Только gepvi_eat_bot уведомления
    assert all(n["sender_method"] == "gepvi_eat_bot" for n in data)
    assert all(n["status"] == "in_progress" for n in data)
    assert data[0]["text"] == "Test notification 1"
    assert data[1]["text"] == "Test notification 2"


@pytest.mark.asyncio
async def test_reserve_notifications_with_report(async_client, session, api_headers):
    """Тест резервации уведомлений с report_id (текст из reports.result)"""
    from app.models import Notification, Task, Report

    user_id = uuid4()

    # Создаем задачу и отчет
    task = Task(
        user_id=user_id,
        next_task_time=datetime.now(timezone.utc),
        period="day"
    )
    session.add(task)
    await session.flush()

    report = Report(
        user_id=user_id,
        report_type="day",
        result="Report AI generated text from LLM",
        task_id=task.id
    )
    session.add(report)
    await session.flush()

    # Создаем уведомление с report_id
    notification = Notification(
        user_id=user_id,
        text="This text should be ignored",
        sender_method="telegram",
        meta={"chat_id": "123456"},
        report_id=report.id
    )
    session.add(notification)
    await session.commit()

    # Резервируем уведомление
    response = await async_client.post(
        "/notifications/reserve",
        json={"sender_method": "telegram", "limit": 100},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "Report AI generated text from LLM"  # Текст из report
    assert data[0]["report_id"] == report.id
    assert data[0]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_reserve_notifications_with_limit(async_client, session, api_headers):
    """Тест резервации с ограничением количества"""
    from app.models import Notification

    user_id = uuid4()

    # Создаем 5 уведомлений
    for i in range(5):
        notification = Notification(
            user_id=user_id,
            text=f"Test notification {i}",
            sender_method="telegram",
            meta={}
        )
        session.add(notification)
    await session.commit()

    # Резервируем только 2
    response = await async_client.post(
        "/notifications/reserve",
        json={"sender_method": "telegram", "limit": 2},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_reserve_notifications_empty(async_client, api_headers):
    """Тест резервации когда нет новых уведомлений"""
    response = await async_client.post(
        "/notifications/reserve",
        json={"sender_method": "telegram", "limit": 100},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


@pytest.mark.asyncio
async def test_mark_notifications_success(async_client, session, api_headers):
    """Тест отметки уведомлений как успешных"""
    from app.models import Notification

    user_id = uuid4()

    # Создаем уведомления в статусе in_progress
    notification1 = Notification(
        user_id=user_id,
        text="Test notification 1",
        sender_method="telegram",
        meta={},
        status="in_progress"
    )
    notification2 = Notification(
        user_id=user_id,
        text="Test notification 2",
        sender_method="telegram",
        meta={},
        status="in_progress"
    )
    session.add_all([notification1, notification2])
    await session.commit()

    # Отмечаем как success
    response = await async_client.post(
        "/notifications/success",
        json={"notification_ids": [notification1.id, notification2.id]},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 2
    assert data["failed_count"] == 0

    # Проверяем что статус изменился
    await session.refresh(notification1)
    await session.refresh(notification2)
    assert notification1.status == "success"
    assert notification2.status == "success"


@pytest.mark.asyncio
async def test_mark_notifications_failed(async_client, session, api_headers):
    """Тест отметки уведомлений как failed"""
    from app.models import Notification

    user_id = uuid4()

    # Создаем уведомления в статусе in_progress
    notification1 = Notification(
        user_id=user_id,
        text="Test notification 1",
        sender_method="telegram",
        meta={},
        status="in_progress"
    )
    notification2 = Notification(
        user_id=user_id,
        text="Test notification 2",
        sender_method="telegram",
        meta={},
        status="in_progress"
    )
    session.add_all([notification1, notification2])
    await session.commit()

    # Отмечаем как failed
    response = await async_client.post(
        "/notifications/success",
        json={"failed_ids": [notification1.id, notification2.id]},
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 0
    assert data["failed_count"] == 2

    # Проверяем что статус изменился на failed
    await session.refresh(notification1)
    await session.refresh(notification2)
    assert notification1.status == "failed"
    assert notification2.status == "failed"


@pytest.mark.asyncio
async def test_mark_notifications_mixed(async_client, session, api_headers):
    """Тест отметки уведомлений с комбинацией success и failed"""
    from app.models import Notification

    user_id = uuid4()

    # Создаем уведомления в статусе in_progress
    notification_success = Notification(
        user_id=user_id,
        text="Success notification",
        sender_method="telegram",
        meta={},
        status="in_progress"
    )
    notification_failed = Notification(
        user_id=user_id,
        text="Failed notification",
        sender_method="telegram",
        meta={},
        status="in_progress"
    )
    session.add_all([notification_success, notification_failed])
    await session.commit()

    # Отмечаем одну как success, другую как failed
    response = await async_client.post(
        "/notifications/success",
        json={
            "notification_ids": [notification_success.id],
            "failed_ids": [notification_failed.id]
        },
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 1
    assert data["failed_count"] == 1

    # Проверяем что статусы изменились правильно
    await session.refresh(notification_success)
    await session.refresh(notification_failed)
    assert notification_success.status == "success"
    assert notification_failed.status == "failed"


@pytest.mark.asyncio
async def test_process_stuck_notifications_retry(session):
    """Тест обработки провисевших уведомлений (ретрай)"""
    from app.models import Notification
    from app.services import process_stuck_notifications

    user_id = uuid4()

    # Создаем уведомление которое провисело больше 5 минут
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    notification = Notification(
        user_id=user_id,
        text="Test notification",
        sender_method="telegram",
        meta={},
        status="in_progress",
        retry_count=0,
        created_at=old_time,
        updated_at=old_time
    )
    session.add(notification)
    await session.commit()

    # Запускаем background job
    await process_stuck_notifications(session)

    # Проверяем что статус изменился на new и retry_count увеличился
    await session.refresh(notification)
    assert notification.status == "new"
    assert notification.retry_count == 1


@pytest.mark.asyncio
async def test_process_stuck_notifications_error(session):
    """Тест обработки провисевших уведомлений (перевод в error)"""
    from app.models import Notification
    from app.services import process_stuck_notifications

    user_id = uuid4()

    # Создаем уведомление которое провисело и уже retry_count = 2
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    notification = Notification(
        user_id=user_id,
        text="Test notification",
        sender_method="telegram",
        meta={},
        status="in_progress",
        retry_count=2,  # Максимальное значение
        created_at=old_time,
        updated_at=old_time
    )
    session.add(notification)
    await session.commit()

    # Запускаем background job
    await process_stuck_notifications(session)

    # Проверяем что статус изменился на error
    await session.refresh(notification)
    assert notification.status == "error"
    assert notification.retry_count == 2  # Не увеличился


@pytest.mark.asyncio
async def test_process_stuck_notifications_fresh(session):
    """Тест что свежие уведомления не трогаем"""
    from app.models import Notification
    from app.services import process_stuck_notifications

    user_id = uuid4()

    # Создаем свежее уведомление (меньше 5 минут)
    notification = Notification(
        user_id=user_id,
        text="Test notification",
        sender_method="telegram",
        meta={},
        status="in_progress",
        retry_count=0
    )
    session.add(notification)
    await session.commit()

    # Запускаем background job
    await process_stuck_notifications(session)

    # Проверяем что ничего не изменилось
    await session.refresh(notification)
    assert notification.status == "in_progress"
    assert notification.retry_count == 0
