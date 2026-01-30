"""API tests for report generation endpoint"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx


@pytest.mark.asyncio
async def test_generate_report_success(async_client, session, api_headers):
    """Test successful report generation"""
    user_id = uuid4()

    mock_report_data = {
        "user_macros_goals": {"calories": 2000, "protein": 150},
        "summary": {"total_calories": 2000, "avg_calories": 2000},
        "meal_components_by_day": [{"date": "2026-01-15", "meals": 3}]
    }

    mock_ai_response = "Ваш дневной отчет готов!"

    with patch("clients.gepvi_eat_client.gepvi_eat_client.get_user_report_data", new=AsyncMock(return_value=mock_report_data)), \
         patch("clients.open_router.open_router_client.generate_report", new=AsyncMock(return_value=mock_ai_response)):

        response = await async_client.post(
            f"/reports/generate/{user_id}",
            json={
                "start_date": "2026-01-15T00:00:00Z",
                "end_date": "2026-01-15T23:59:59Z",
                "period": "day",
                "sender_method": "telegram"
            },
            headers=api_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(user_id)
        assert data["report_type"] == "day"
        assert data["result"] == mock_ai_response
        assert "id" in data
        assert "created_at" in data

        # Verify notification was created
        from app.models import Notification
        from sqlalchemy import select
        stmt = select(Notification).where(Notification.user_id == user_id)
        result = await session.execute(stmt)
        notifications = result.scalars().all()
        assert len(notifications) == 1
        assert notifications[0].report_id == data["id"]
        assert notifications[0].sender_method == "telegram"
        assert notifications[0].status == "new"


@pytest.mark.asyncio
async def test_generate_report_invalid_period(async_client, api_headers):
    """Test validation error for invalid period"""
    user_id = uuid4()

    response = await async_client.post(
        f"/reports/generate/{user_id}",
        json={
            "start_date": "2026-01-15T00:00:00Z",
            "end_date": "2026-01-15T23:59:59Z",
            "period": "yearly",  # Invalid
            "sender_method": "telegram"
        },
        headers=api_headers
    )

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_generate_report_no_data(async_client, api_headers):
    """Test error when no data available"""
    user_id = uuid4()

    mock_empty_data = {
        "summary": None,
        "meal_components_by_day": []
    }

    with patch("clients.gepvi_eat_client.gepvi_eat_client.get_user_report_data", new=AsyncMock(return_value=mock_empty_data)):
        response = await async_client.post(
            f"/reports/generate/{user_id}",
            json={
                "start_date": "2026-01-15T00:00:00Z",
                "end_date": "2026-01-15T23:59:59Z",
                "period": "day",
                "sender_method": "telegram"
            },
            headers=api_headers
        )

        assert response.status_code == 400
        data = response.json()
        assert "Insufficient data" in data["detail"]


@pytest.mark.asyncio
async def test_generate_report_gepvi_eat_down(async_client, api_headers):
    """Test error when gepvi_eat service is down"""
    user_id = uuid4()

    mock_error = httpx.HTTPStatusError(
        "Service unavailable",
        request=AsyncMock(),
        response=AsyncMock(status_code=503)
    )

    with patch("clients.gepvi_eat_client.gepvi_eat_client.get_user_report_data", new=AsyncMock(side_effect=mock_error)):
        response = await async_client.post(
            f"/reports/generate/{user_id}",
            json={
                "start_date": "2026-01-15T00:00:00Z",
                "end_date": "2026-01-15T23:59:59Z",
                "period": "day",
                "sender_method": "telegram"
            },
            headers=api_headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "Internal Server Error" in data["detail"]


@pytest.mark.asyncio
async def test_generate_report_ai_failure(async_client, api_headers):
    """Test error when AI generation fails"""
    user_id = uuid4()

    mock_report_data = {
        "user_macros_goals": {"calories": 2000},
        "summary": {"total_calories": 2000},
        "meal_components_by_day": [{"date": "2026-01-15", "components": [{"name": "Test", "W": 100}]}]
    }

    ai_error = Exception("AI model timeout")

    with patch("clients.gepvi_eat_client.gepvi_eat_client.get_user_report_data", new=AsyncMock(return_value=mock_report_data)), \
         patch("clients.open_router.open_router_client.generate_report", new=AsyncMock(side_effect=ai_error)):

        response = await async_client.post(
            f"/reports/generate/{user_id}",
            json={
                "start_date": "2026-01-15T00:00:00Z",
                "end_date": "2026-01-15T23:59:59Z",
                "period": "day",
                "sender_method": "telegram"
            },
            headers=api_headers
        )

        assert response.status_code == 400
        data = response.json()
        assert "Could not generate AI report" in data["detail"]


@pytest.mark.asyncio
async def test_generate_weekly_report(async_client, api_headers):
    """Test weekly report generation"""
    user_id = uuid4()

    mock_report_data = {
        "user_macros_goals": {"calories": 2000},
        "summary": {"total_calories": 14000, "avg_calories": 2000},
        "meal_components_by_day": [{"date": f"2026-01-{i:02d}", "meals": 3} for i in range(1, 8)]
    }

    mock_ai_response = "Ваш недельный отчет с анализом"

    with patch("clients.gepvi_eat_client.gepvi_eat_client.get_user_report_data", new=AsyncMock(return_value=mock_report_data)), \
         patch("clients.open_router.open_router_client.generate_report", new=AsyncMock(return_value=mock_ai_response)):

        response = await async_client.post(
            f"/reports/generate/{user_id}",
            json={
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-01-07T23:59:59Z",
                "period": "week",
                "sender_method": "telegram"
            },
            headers=api_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["report_type"] == "week"


@pytest.mark.asyncio
async def test_generate_report_notification_meta(async_client, session, api_headers):
    """Test that notification meta contains correct report metadata"""
    user_id = uuid4()

    mock_report_data = {
        "user_macros_goals": {},
        "summary": {"total_calories": 2000},
        "meal_components_by_day": [{"date": "2026-01-15", "components": [{"name": "Test", "W": 100}]}]
    }

    mock_ai_response = "A" * 200  # Long response to test preview

    with patch("clients.gepvi_eat_client.gepvi_eat_client.get_user_report_data", new=AsyncMock(return_value=mock_report_data)), \
         patch("clients.open_router.open_router_client.generate_report", new=AsyncMock(return_value=mock_ai_response)):

        response = await async_client.post(
            f"/reports/generate/{user_id}",
            json={
                "start_date": "2026-01-15T00:00:00Z",
                "end_date": "2026-01-15T23:59:59Z",
                "period": "day",
                "sender_method": "telegram"
            },
            headers=api_headers
        )

        assert response.status_code == 201

        # Check notification meta
        from app.models import Notification
        from sqlalchemy import select
        stmt = select(Notification).where(Notification.user_id == user_id)
        result = await session.execute(stmt)
        notification = result.scalar_one()

        assert notification.meta["period"] == "day"
        assert "start_date" in notification.meta
        assert "end_date" in notification.meta
