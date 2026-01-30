"""HTTP client for gepvi_eat microservice (server-to-server communication)"""
import logging
from datetime import datetime
from uuid import UUID

import httpx

from settings.config import AppConfig

logger = logging.getLogger(__name__)


class GepviEatClient:
    """Client for gepvi_eat microservice"""

    def __init__(self):
        self.base_url = AppConfig.EAT_SERVICE_URL
        self.timeout = 30.0
        self.api_key = AppConfig.API_KEY

    def _get_headers(self) -> dict:
        """Get headers with API key"""
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def get_user_report_data(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> dict:
        """Get user report data from gepvi_eat service. No caching - always fresh data."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/users/{user_id}/report_data",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()


# Singleton instance
gepvi_eat_client = GepviEatClient()
