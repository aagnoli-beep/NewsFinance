"""API endpoints per event_clusters classificati + entities + expectations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.entities import Entity
from app.models.events import EventCluster, EventEntity, Expectation, RawEvent

router = APIRouter(prefix="/clusters", tags=["clusters"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class EntityOut(BaseModel):
    id: int
    type: str
    name: str
    ticker: str | None
    role: str


class ExpectationOut(BaseModel):
    baseline_source: str
    expected_value: str | None
    actual_value: str | None
    surprise_direction: str
    surprise_magnitude: str
    surprise_zscore: float | None
    rationale: str | None


class ClusterOut(BaseModel):
    id: int
    first_seen: datetime
    event_type: str
    headline_canonical: str
    summary: str | None
    novelty_score: float
    n_sources: int
    entities: list[EntityOut]
    expectation: ExpectationOut | None


class ClusterListResponse(BaseModel):
    items: list[ClusterOut]
    total: int


class ClusterStats(BaseModel):
    total_clusters: int
    classified: int
    with_expectations: int
    by_type: list[dict]


@router.get("", response_model=ClusterListResponse)
async def list_clusters(
    session: SessionDep,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None),
    only_classified: bool = Query(default=True),
) -> ClusterListResponse:
    base = select(EventCluster)
    if only_classified:
        base = base.where(EventCluster.event_type != "unclassified")
    if event_type:
        base = base.where(EventCluster.event_type == event_type)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    rows = (
        await session.execute(
            base.order_by(desc(EventCluster.first_seen)).limit(limit).offset(offset)
        )
    ).scalars().all()

    items: list[ClusterOut] = []
    for cluster in rows:
        n_sources = (
            await session.execute(
                select(func.count())
                .select_from(RawEvent)
                .where(RawEvent.cluster_id == cluster.id)
            )
        ).scalar() or 0

        entity_rows = (
            await session.execute(
                select(Entity, EventEntity.role)
                .join(EventEntity, EventEntity.entity_id == Entity.id)
                .where(EventEntity.cluster_id == cluster.id)
            )
        ).all()

        entities = [
            EntityOut(
                id=e.id,
                type=e.type,
                name=e.name,
                ticker=e.ticker,
                role=role,
            )
            for e, role in entity_rows
        ]

        exp = (
            await session.execute(
                select(Expectation).where(Expectation.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

        expectation = (
            ExpectationOut(
                baseline_source=exp.baseline_source,
                expected_value=exp.expected_value,
                actual_value=exp.actual_value,
                surprise_direction=exp.surprise_direction,
                surprise_magnitude=exp.surprise_magnitude,
                surprise_zscore=exp.surprise_zscore,
                rationale=exp.rationale,
            )
            if exp
            else None
        )

        items.append(
            ClusterOut(
                id=cluster.id,
                first_seen=cluster.first_seen,
                event_type=cluster.event_type,
                headline_canonical=cluster.headline_canonical,
                summary=cluster.summary,
                novelty_score=cluster.novelty_score,
                n_sources=n_sources,
                entities=entities,
                expectation=expectation,
            )
        )

    return ClusterListResponse(items=items, total=total)


@router.get("/stats", response_model=ClusterStats)
async def cluster_stats(session: SessionDep) -> ClusterStats:
    total = (await session.execute(select(func.count()).select_from(EventCluster))).scalar() or 0
    classified = (
        await session.execute(
            select(func.count())
            .select_from(EventCluster)
            .where(EventCluster.event_type != "unclassified")
        )
    ).scalar() or 0
    with_exp = (
        await session.execute(select(func.count()).select_from(Expectation))
    ).scalar() or 0

    by_type_rows = (
        await session.execute(
            select(EventCluster.event_type, func.count().label("n"))
            .group_by(EventCluster.event_type)
            .order_by(desc("n"))
        )
    ).all()
    by_type = [{"event_type": t, "count": n} for t, n in by_type_rows]

    return ClusterStats(
        total_clusters=total,
        classified=classified,
        with_expectations=with_exp,
        by_type=by_type,
    )


@router.get("/{cluster_id}", response_model=ClusterOut)
async def get_cluster(cluster_id: int, session: SessionDep) -> ClusterOut:
    cluster = (
        await session.execute(select(EventCluster).where(EventCluster.id == cluster_id))
    ).scalar_one_or_none()
    if cluster is None:
        raise HTTPException(status_code=404, detail="cluster_not_found")

    n_sources = (
        await session.execute(
            select(func.count())
            .select_from(RawEvent)
            .where(RawEvent.cluster_id == cluster.id)
        )
    ).scalar() or 0

    entity_rows = (
        await session.execute(
            select(Entity, EventEntity.role)
            .join(EventEntity, EventEntity.entity_id == Entity.id)
            .where(EventEntity.cluster_id == cluster.id)
        )
    ).all()
    entities = [
        EntityOut(id=e.id, type=e.type, name=e.name, ticker=e.ticker, role=role)
        for e, role in entity_rows
    ]

    exp = (
        await session.execute(select(Expectation).where(Expectation.cluster_id == cluster.id))
    ).scalar_one_or_none()
    expectation = (
        ExpectationOut(
            baseline_source=exp.baseline_source,
            expected_value=exp.expected_value,
            actual_value=exp.actual_value,
            surprise_direction=exp.surprise_direction,
            surprise_magnitude=exp.surprise_magnitude,
            surprise_zscore=exp.surprise_zscore,
            rationale=exp.rationale,
        )
        if exp
        else None
    )

    return ClusterOut(
        id=cluster.id,
        first_seen=cluster.first_seen,
        event_type=cluster.event_type,
        headline_canonical=cluster.headline_canonical,
        summary=cluster.summary,
        novelty_score=cluster.novelty_score,
        n_sources=n_sources,
        entities=entities,
        expectation=expectation,
    )
