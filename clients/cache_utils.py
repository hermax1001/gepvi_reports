"""Simple TTL cache implementation for async functions"""
import asyncio
import time
from typing import Optional, Any, Dict, Tuple
from functools import wraps


class TTLCache:
    """Simple in-memory TTL cache for async functions"""

    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        async with self._lock:
            if key in self._cache:
                value, expiry_time = self._cache[key]
                if time.time() < expiry_time:
                    return value
                else:
                    # Expired, remove it
                    del self._cache[key]
            return None

    async def set(self, key: str, value: Any, ttl: int):
        """Set value in cache with TTL in seconds"""
        async with self._lock:
            expiry_time = time.time() + ttl
            self._cache[key] = (value, expiry_time)

    async def clear(self):
        """Clear all cache"""
        async with self._lock:
            self._cache.clear()


def async_ttl_cache(ttl: int):
    """Decorator for caching async function results with TTL"""
    cache = TTLCache()

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result

        # Add method to clear cache
        wrapper.clear_cache = cache.clear
        return wrapper

    return decorator
