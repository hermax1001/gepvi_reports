"""HTTP client for gepvi_users microservice (server-to-server communication)"""
import logging
from uuid import UUID

import httpx

from settings.config import AppConfig
from clients.cache_utils import async_ttl_cache

logger = logging.getLogger(__name__)


class GepviUsersClient:
    """Client for gepvi_users microservice"""

    def __init__(self):
        self.base_url = AppConfig.USERS_SERVICE_URL
        self.timeout = 30.0
        self.api_key = AppConfig.API_KEY

    def _get_headers(self) -> dict:
        """Get headers with API key"""
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    @async_ttl_cache(ttl=10)
    async def get_or_create_user(self, telegram_user_id: str) -> dict:
        """Get or create user in gepvi_users service. Returns dict with user_id (UUID) and telegram_user_id. Cached for 60 seconds."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/users/get_or_create",
                json={"telegram_user_id": telegram_user_id},
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

    @async_ttl_cache(ttl=10)
    async def get_user_by_user_id(self, user_id: UUID) -> dict:
        """Get user by internal user_id (UUID). Returns dict with user_id, telegram_user_id, and has_active_subscription. Cached for 60 seconds."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/users/{user_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

    async def create_payment(
        self,
        telegram_user_id: str,
        package_type: str,
        return_url: str
    ) -> dict:
        """Create payment for subscription"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/payments/create",
                json={
                    "telegram_user_id": telegram_user_id,
                    "package_type": package_type,
                    "return_url": return_url
                },
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

    async def update_user(
        self,
        user_id: UUID,
        timezone: str | None = None,
        yob: int | None = None,
        weight: float | None = None,
        gender: str | None = None,
        height: int | None = None,
        activity_level: float | None = None
    ) -> dict:
        """Update user profile data. Returns updated user with all fields."""
        payload = {}
        if timezone is not None:
            payload["timezone"] = timezone
        if yob is not None:
            payload["yob"] = yob
        if weight is not None:
            payload["weight"] = weight
        if gender is not None:
            payload["gender"] = gender
        if height is not None:
            payload["height"] = height
        if activity_level is not None:
            payload["activity_level"] = activity_level

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(
                f"{self.base_url}/users/{user_id}",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()


# Singleton instance
gepvi_users_client = GepviUsersClient()
