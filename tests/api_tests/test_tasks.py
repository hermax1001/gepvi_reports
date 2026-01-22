"""API тесты для задач"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_get_tasks_by_user_id_empty(async_client, api_headers):
    """Тест получения задач для пользователя без задач"""
    user_id = uuid4()

    response = await async_client.get(
        f"/tasks/user/{user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_get_tasks_by_user_id_with_data(async_client, session, api_headers):
    """Тест получения задач для пользователя с данными"""
    from app.models import Task

    user_id = uuid4()
    next_task_time = datetime.now(timezone.utc)

    # Создаем задачу
    task = Task(
        user_id=user_id,
        next_task_time=next_task_time,
        period="week"
    )
    session.add(task)
    await session.commit()

    # Запрашиваем задачи
    response = await async_client.get(
        f"/tasks/user/{user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["user_id"] == str(user_id)
    assert data[0]["period"] == "week"
