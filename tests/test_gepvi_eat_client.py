"""Tests for GepviEat HTTP client"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import httpx


@pytest.mark.asyncio
async def test_get_user_report_data_success():
    """Test successful data fetch from gepvi_eat"""
    from clients.gepvi_eat_client import GepviEatClient

    user_id = uuid4()
    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 31, tzinfo=timezone.utc)

    expected_data = {
        "user_macros_goals": {"calories": 2000, "protein": 150},
        "summary": {"total_calories": 62000, "avg_calories": 2000},
        "meal_components_by_day": [{"date": "2026-01-01", "meals": 3}]
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=expected_data)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = mock_client

        client = GepviEatClient()
        result = await client.get_user_report_data(user_id, start_date, end_date)

        assert result == expected_data
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert str(user_id) in call_args[0][0]
        assert call_args[1]["params"]["start_date"] == start_date.isoformat()
        assert call_args[1]["params"]["end_date"] == end_date.isoformat()


@pytest.mark.asyncio
async def test_get_user_report_data_http_error():
    """Test HTTP error handling"""
    from clients.gepvi_eat_client import GepviEatClient

    user_id = uuid4()
    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 31, tzinfo=timezone.utc)

    with patch("httpx.AsyncClient") as mock_client_class:
        def raise_error():
            raise httpx.HTTPStatusError(
                "Service unavailable",
                request=MagicMock(),
                response=MagicMock(status_code=503)
            )

        mock_response = MagicMock()
        mock_response.raise_for_status = raise_error

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = mock_client

        client = GepviEatClient()
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_user_report_data(user_id, start_date, end_date)


@pytest.mark.asyncio
async def test_get_user_report_data_correct_url_params():
    """Verify correct URL and parameters are used"""
    from clients.gepvi_eat_client import GepviEatClient

    user_id = uuid4()
    start_date = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 20, 15, 45, tzinfo=timezone.utc)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={"summary": {}})
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = mock_client

        client = GepviEatClient()
        await client.get_user_report_data(user_id, start_date, end_date)

        call_args = mock_client.get.call_args
        url = call_args[0][0]
        params = call_args[1]["params"]

        assert f"/users/{user_id}/report_data" in url
        assert params["start_date"] == "2026-01-15T10:30:00+00:00"
        assert params["end_date"] == "2026-01-20T15:45:00+00:00"
