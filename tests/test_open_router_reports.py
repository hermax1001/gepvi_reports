"""Tests for OpenRouter report generation"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


def create_mock_httpx_client(response_data=None, error=None):
    """Helper to create properly mocked httpx.AsyncClient"""
    if error:
        def raise_error():
            raise error

        mock_response = MagicMock()
        mock_response.raise_for_status = raise_error
    else:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=response_data)
        mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


@pytest.mark.asyncio
async def test_generate_daily_report():
    """Test daily report generation uses correct prompt"""
    from clients.open_router import OpenRouterClient, DAILY_REPORT_PROMPT

    start_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    user_goals = {"calories": 2000}
    summary = {"total_calories": 1950}
    daily_components = [{"date": "2026-01-15", "meals": 3}]

    expected_response = "Ваш дневной отчет: всё хорошо!"

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = create_mock_httpx_client({
            "choices": [{"message": {"content": expected_response}}]
        })
        mock_client_class.return_value = mock_client

        client = OpenRouterClient()
        result = await client.generate_report(
            period="day",
            start_date=start_date,
            end_date=end_date,
            user_goals=user_goals,
            summary=summary,
            daily_components=daily_components
        )

        assert result == expected_response
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]

        # Verify daily prompt was used (check for distinctive daily phrases)
        prompt_text = payload["messages"][0]["content"]
        assert "Максимум 300 слов" in prompt_text
        assert "НЕ делай долгосрочных выводов" in prompt_text


@pytest.mark.asyncio
async def test_generate_weekly_report():
    """Test weekly report generation uses detailed prompt"""
    from clients.open_router import OpenRouterClient, WEEKLY_MONTHLY_REPORT_PROMPT

    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 7, tzinfo=timezone.utc)
    user_goals = {"calories": 2000, "protein": 150}
    summary = {"total_calories": 14000, "avg_calories": 2000}
    daily_components = [{"date": f"2026-01-0{i}", "meals": 3} for i in range(1, 8)]

    expected_response = "Недельный отчет с анализом трендов"

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = create_mock_httpx_client({
            "choices": [{"message": {"content": expected_response}}]
        })
        mock_client_class.return_value = mock_client

        client = OpenRouterClient()
        result = await client.generate_report(
            period="week",
            start_date=start_date,
            end_date=end_date,
            user_goals=user_goals,
            summary=summary,
            daily_components=daily_components
        )

        assert result == expected_response
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]

        # Verify weekly/monthly prompt was used
        prompt_text = payload["messages"][0]["content"]
        assert "Максимум 800 слов" in prompt_text
        assert "АНАЛИЗ ПАТТЕРНОВ" in prompt_text
        assert "тренды по дням" in prompt_text


@pytest.mark.asyncio
async def test_generate_monthly_report():
    """Test monthly report generation"""
    from clients.open_router import OpenRouterClient

    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 31, tzinfo=timezone.utc)
    user_goals = {"calories": 2000}
    summary = {"total_calories": 62000}
    daily_components = []

    expected_response = "Месячный отчет"

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = create_mock_httpx_client({
            "choices": [{"message": {"content": expected_response}}]
        })
        mock_client_class.return_value = mock_client

        client = OpenRouterClient()
        result = await client.generate_report(
            period="month",
            start_date=start_date,
            end_date=end_date,
            user_goals=user_goals,
            summary=summary,
            daily_components=daily_components
        )

        assert result == expected_response


@pytest.mark.asyncio
async def test_generate_report_ai_failure():
    """Test AI generation failure handling"""
    from clients.open_router import OpenRouterClient

    start_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 15, tzinfo=timezone.utc)

    error = httpx.HTTPStatusError(
        "Rate limited",
        request=AsyncMock(),
        response=AsyncMock(status_code=429)
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = create_mock_httpx_client(error=error)
        mock_client_class.return_value = mock_client

        client = OpenRouterClient()
        with pytest.raises(httpx.HTTPStatusError):
            await client.generate_report(
                period="day",
                start_date=start_date,
                end_date=end_date,
                user_goals={},
                summary={},
                daily_components=[]
            )


@pytest.mark.asyncio
async def test_generate_report_parameters():
    """Test that correct parameters are passed to AI"""
    from clients.open_router import OpenRouterClient

    start_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 15, tzinfo=timezone.utc)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = create_mock_httpx_client({
            "choices": [{"message": {"content": "test"}}]
        })
        mock_client_class.return_value = mock_client

        client = OpenRouterClient()
        await client.generate_report(
            period="day",
            start_date=start_date,
            end_date=end_date,
            user_goals={},
            summary={},
            daily_components=[]
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]

        # Verify correct parameters
        assert payload["max_tokens"] == 2000
        assert payload["temperature"] == 0.5
        assert "model" in payload
        assert "messages" in payload
