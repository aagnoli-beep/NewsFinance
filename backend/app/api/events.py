"""API endpoints per Raw Feed + cluster di eventi."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.events import EventCluster, RawEvent

router = APIRouter(prefix="/events", tags=["events"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class RawEventOut(BaseModel):
    id: int
    source: str
    source_quality: str
    headline: str
    body: str | None
    source_url: str | None
    published_at: datetime | None
    ingested_at: datetime
    cluster_id: int | None
    raw_meta: dict


class FeedResponse(BaseModel):
    items: list[RawEventOut]
    total: int
    has_more: bool


class SourceCount(BaseModel):
    source: str
    count: int


class FeedStats(BaseModel):
    total_events: int
    total_clusters: int
    pending_dedup: int
    last_24h: int
    sources: list[SourceCount]


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    source: str | None = Query(default=None, description="Filtro per prefix source (es. 'rss', 'polygon')"),
) -> FeedResponse:
    """Stream di raw_events più recenti, paginato e filtrabile per source."""
    base = select(RawEvent)
    if source:
        base = base.where(RawEvent.source.like(f"{source}%"))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    result = await session.execute(
        base.order_by(desc(RawEvent.ingested_at)).limit(limit).offset(offset)
    )
    rows = list(result.scalars().all())

    items = [
        RawEventOut(
            id=r.id,
            source=r.source,
            source_quality=r.source_quality,
            headline=r.headline,
            body=r.body,
            source_url=r.source_url,
            published_at=r.published_at,
            ingested_at=r.ingested_at,
            cluster_id=r.cluster_id,
            raw_meta=r.raw_meta or {},
        )
        for r in rows
    ]
    return FeedResponse(items=items, total=total, has_more=(offset + len(items) < total))


@router.get("/stats", response_model=FeedStats)
async def get_stats(session: SessionDep) -> FeedStats:
    """Statistiche aggregate per il pannello status del frontend."""
    total = (await session.execute(select(func.count()).select_from(RawEvent))).scalar() or 0
    clusters = (await session.execute(select(func.count()).select_from(EventCluster))).scalar() or 0
    pending = (
        await session.execute(
            select(func.count()).select_from(RawEvent).where(RawEvent.cluster_id.is_(None))
        )
    ).scalar() or 0

    last_24h_q = select(func.count()).select_from(RawEvent).where(
        RawEvent.ingested_at >= func.now() - func.make_interval(0, 0, 0, 1)
    )
    last_24h = (await session.execute(last_24h_q)).scalar() or 0

    src_q = (
        select(RawEvent.source, func.count().label("c"))
        .group_by(RawEvent.source)
        .order_by(desc("c"))
    )
    src_rows = (await session.execute(src_q)).all()

    return FeedStats(
        total_events=total,
        total_clusters=clusters,
        pending_dedup=pending,
        last_24h=last_24h,
        sources=[SourceCount(source=s, count=c) for s, c in src_rows],
    )
