from redis.asyncio import Redis, from_url

from app.core.config import get_settings


def get_redis() -> Redis:
    settings = get_settings()
    return from_url(settings.redis_url, decode_responses=True)
