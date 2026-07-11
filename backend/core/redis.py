"""Redis client factory used for caching, rate limiting, and Celery result polling."""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as aioredis
from redis import Redis

from backend.core.config import settings


@lru_cache
def get_redis_client() -> Redis:
    """Return a cached synchronous Redis client."""
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


@lru_cache
def get_async_redis_client() -> aioredis.Redis:
    """Return a cached asyncio Redis client."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)
