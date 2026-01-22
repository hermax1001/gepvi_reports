"""API тесты для отчетов"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_get_reports_by_user_id_empty(async_client, api_headers):
    """Тест получения отчетов для пользователя без отчетов"""
    user_id = uuid4()

    response = await async_client.get(
        f"/reports/user/{user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_get_reports_by_user_id_with_data(async_client, session, api_headers):
    """Тест получения отчетов для пользователя с данными"""
    from app.models import Task, Report

    user_id = uuid4()

    # Создаем задачу
    task = Task(
        user_id=user_id,
        next_task_time=datetime.now(timezone.utc),
        period="day"
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    # Создаем отчет
    report = Report(
        user_id=user_id,
        report_type="day",
        result="Test report result",
        task_id=task.id
    )
    session.add(report)
    await session.commit()

    # Запрашиваем отчеты
    response = await async_client.get(
        f"/reports/user/{user_id}",
        headers=api_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["user_id"] == str(user_id)
    assert data[0]["report_type"] == "day"
    assert data[0]["result"] == "Test report result"
    assert data[0]["task_id"] == task.id
