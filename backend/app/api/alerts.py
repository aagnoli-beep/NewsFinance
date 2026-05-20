"""API endpoints per Alerts + performance/calibration dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.calibration import CalibrationAgent
from app.core.db import get_session
from app.models.alerts import Alert, Outcome
from app.models.entities import Entity
from app.models.events import (
    EventCluster,
    EventEntity,
    Expectation,
    Exposure,
)
from app.models.market import Confounder, MarketReaction

router = APIRouter(prefix="/alerts", tags=["alerts"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class AlertEntity(BaseModel):
    id: int
    name: str
    ticker: str | None
    role: str


class AlertExposure(BaseModel):
    asset_ticker: str
    exposure_type: str
    hop_distance: int
    weight: float
    rationale: str | None


class AlertReaction(BaseModel):
    ticker: str
    abnormal_return_1d: float | None
    abnormal_return_3d: float | None
    volume_zscore: float | None
    market_confirmation: str | None


class AlertExpectation(BaseModel):
    surprise_direction: str
    surprise_magnitude: str
    rationale: str | None


class AlertOutcome(BaseModel):
    t_plus_1d_ar: float | None
    t_plus_3d_ar: float | None
    t_plus_7d_ar: float | None
    t_plus_30d_ar: float | None
    outcome_label: str
    evaluated_at: datetime | None


class AlertOut(BaseModel):
    id: int
    cluster_id: int
    created_at: datetime
    impact_score: float
    confidence: float
    explanation_md: str
    components: dict
    event_type: str
    headline: str
    summary: str | None
    first_seen: datetime
    novelty_score: float
    primary_entities: list[AlertEntity]
    exposures: list[AlertExposure]
    reactions: list[AlertReaction]
    expectation: AlertExpectation | None
    outcome: AlertOutcome | None
    confounder_count: int
    max_confounder_score: float | None


class AlertListResponse(BaseModel):
    items: list[AlertOut]
    total: int


class AlertsStats(BaseModel):
    total_alerts: int
    last_24h: int
    last_7d: int
    avg_impact_score: float | None
    outcomes: dict
    precision_3d: float | None


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    session: SessionDep,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
) -> AlertListResponse:
    base = select(Alert).where(Alert.impact_score >= min_score)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    rows = (
        await session.execute(
            base.order_by(desc(Alert.created_at)).limit(limit).offset(offset)
        )
    ).scalars().all()

    items: list[AlertOut] = []
    for alert in rows:
        items.append(await _hydrate_alert(session, alert))
    return AlertListResponse(items=items, total=total)


@router.get("/stats", response_model=AlertsStats)
async def alerts_stats(session: SessionDep) -> AlertsStats:
    total = (await session.execute(select(func.count()).select_from(Alert))).scalar() or 0

    last_24h = (
        await session.execute(
            select(func.count())
            .select_from(Alert)
            .where(Alert.created_at >= func.now() - func.make_interval(0, 0, 0, 1))
        )
    ).scalar() or 0

    last_7d = (
        await session.execute(
            select(func.count())
            .select_from(Alert)
            .where(Alert.created_at >= func.now() - func.make_interval(0, 0, 0, 7))
        )
    ).scalar() or 0

    avg_score = (
        await session.execute(select(func.avg(Alert.impact_score)))
    ).scalar()

    outcome_rows = (
        await session.execute(
            select(Outcome.outcome_label, func.count())
            .group_by(Outcome.outcome_label)
        )
    ).all()
    outcomes = {label: count for label, count in outcome_rows}

    confirmed = outcomes.get("confirmed_direction", 0)
    reversed_ = outcomes.get("reversed", 0)
    precision_3d = (
        confirmed / (confirmed + reversed_) if (confirmed + reversed_) > 0 else None
    )

    return AlertsStats(
        total_alerts=total,
        last_24h=last_24h,
        last_7d=last_7d,
        avg_impact_score=float(avg_score) if avg_score is not None else None,
        outcomes=outcomes,
        precision_3d=round(precision_3d, 3) if precision_3d is not None else None,
    )


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: int, session: SessionDep) -> AlertOut:
    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="alert_not_found")
    return await _hydrate_alert(session, alert)


@router.get("/calibration/report")
async def calibration_report(session: SessionDep) -> dict:
    """Esegue (ricalcolo on-demand) il calibration report."""
    return await CalibrationAgent(session).run()


async def _hydrate_alert(session: AsyncSession, alert: Alert) -> AlertOut:
    cluster = (
        await session.execute(select(EventCluster).where(EventCluster.id == alert.cluster_id))
    ).scalar_one()

    entity_rows = (
        await session.execute(
            select(Entity, EventEntity.role)
            .join(EventEntity, EventEntity.entity_id == Entity.id)
            .where(EventEntity.cluster_id == cluster.id)
            .where(EventEntity.role == "primary")
        )
    ).all()
    primary_entities = [
        AlertEntity(id=e.id, name=e.name, ticker=e.ticker, role=role)
        for e, role in entity_rows
    ]

    exposure_rows = (
        await session.execute(
            select(Exposure).where(Exposure.cluster_id == cluster.id).order_by(desc(Exposure.weight))
        )
    ).scalars().all()
    exposures = [
        AlertExposure(
            asset_ticker=ex.asset_ticker,
            exposure_type=ex.exposure_type,
            hop_distance=ex.hop_distance,
            weight=ex.weight,
            rationale=ex.rationale,
        )
        for ex in exposure_rows
    ]

    reaction_rows = (
        await session.execute(
            select(MarketReaction).where(MarketReaction.cluster_id == cluster.id)
        )
    ).scalars().all()
    reactions = [
        AlertReaction(
            ticker=r.ticker,
            abnormal_return_1d=r.abnormal_return_1d,
            abnormal_return_3d=r.abnormal_return_3d,
            volume_zscore=r.volume_zscore,
            market_confirmation=r.market_confirmation,
        )
        for r in reaction_rows
    ]

    exp = (
        await session.execute(
            select(Expectation).where(Expectation.cluster_id == cluster.id)
        )
    ).scalar_one_or_none()
    expectation = (
        AlertExpectation(
            surprise_direction=exp.surprise_direction,
            surprise_magnitude=exp.surprise_magnitude,
            rationale=exp.rationale,
        )
        if exp
        else None
    )

    outcome = (
        await session.execute(select(Outcome).where(Outcome.alert_id == alert.id))
    ).scalar_one_or_none()
    outcome_out = (
        AlertOutcome(
            t_plus_1d_ar=outcome.t_plus_1d_ar,
            t_plus_3d_ar=outcome.t_plus_3d_ar,
            t_plus_7d_ar=outcome.t_plus_7d_ar,
            t_plus_30d_ar=outcome.t_plus_30d_ar,
            outcome_label=outcome.outcome_label,
            evaluated_at=outcome.evaluated_at,
        )
        if outcome
        else None
    )

    confounder_count = (
        await session.execute(
            select(func.count())
            .select_from(Confounder)
            .where(Confounder.cluster_id == cluster.id)
        )
    ).scalar() or 0
    max_conf = (
        await session.execute(
            select(func.max(Confounder.materiality_score)).where(
                Confounder.cluster_id == cluster.id
            )
        )
    ).scalar()

    return AlertOut(
        id=alert.id,
        cluster_id=alert.cluster_id,
        created_at=alert.created_at,
        impact_score=alert.impact_score,
        confidence=alert.confidence,
        explanation_md=alert.explanation_md,
        components=alert.components or {},
        event_type=cluster.event_type,
        headline=cluster.headline_canonical,
        summary=cluster.summary,
        first_seen=cluster.first_seen,
        novelty_score=cluster.novelty_score,
        primary_entities=primary_entities,
        exposures=exposures,
        reactions=reactions,
        expectation=expectation,
        outcome=outcome_out,
        confounder_count=confounder_count,
        max_confounder_score=float(max_conf) if max_conf is not None else None,
    )
