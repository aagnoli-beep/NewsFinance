from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.redis_client import get_redis

router = APIRouter(tags=["system"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/full")
async def health_full(session: SessionDep) -> dict:
    db_ok = False
    redis_ok = False

    try:
        result = await session.execute(text("SELECT 1"))
        db_ok = result.scalar() == 1
    except Exception:
        db_ok = False

    try:
        redis = get_redis()
        pong = await redis.ping()
        redis_ok = bool(pong)
        await redis.aclose()
    except Exception:
        redis_ok = False

    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "checks": {"database": db_ok, "redis": redis_ok},
    }
