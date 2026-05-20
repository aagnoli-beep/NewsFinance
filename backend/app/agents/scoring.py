"""Scoring engine — combina novelty, surprise, exposure, market confirmation,
source quality, confounder penalty in un impact_score.

Formula:
    base = w_novelty * novelty + w_surprise * surprise + w_exposure * max_exposure_weight
           + w_confirm * market_confirmation + w_source * source_quality

    impact_score = base * (1 - confounder_penalty)

Pesi iniziali (saranno calibrati dal calibration_agent in Phase 8):
    w_novelty   = 0.15
    w_surprise  = 0.30
    w_exposure  = 0.20
    w_confirm   = 0.25
    w_source    = 0.10
    max confounder_penalty = 0.5

Mapping numerico:
    surprise_magnitude: low=0.3, medium=0.6, high=1.0
    surprise_direction: positive/negative=1.0, neutral=0.5, uncertain=0.3
    confirmation: did_react=1.0, unclear=0.5, did_not_react=0.0
    source_quality: official=1.0, primary=0.85, secondary=0.65, social=0.3, rumor=0.2

Soglia alert: impact_score >= 0.65 → genera Alert. Sotto: log + skip.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alerts import Alert
from app.models.events import EventCluster, Expectation, Exposure, RawEvent
from app.models.market import Confounder, MarketReaction

WEIGHTS = {
    "novelty": 0.15,
    "surprise": 0.30,
    "exposure": 0.20,
    "confirm": 0.25,
    "source": 0.10,
}

ALERT_THRESHOLD = 0.65

SURPRISE_MAGNITUDE_MAP = {"low": 0.3, "medium": 0.6, "high": 1.0}
SURPRISE_DIRECTION_MAP = {
    "positive": 1.0,
    "negative": 1.0,
    "neutral": 0.5,
    "uncertain": 0.3,
}
CONFIRMATION_MAP = {
    "did_react": 1.0,
    "unclear": 0.5,
    "did_not_react": 0.0,
}
SOURCE_QUALITY_MAP = {
    "official": 1.0,
    "primary": 0.85,
    "secondary": 0.65,
    "social": 0.3,
    "rumor": 0.2,
}


class ScoringEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_pending(self, limit: int = 100) -> dict[str, int]:
        """Calcola impact_score per cluster classificati senza alert."""
        pending = await self._fetch_pending(limit)
        if not pending:
            return {
                "computed": 0,
                "alerts_generated": 0,
                "below_threshold": 0,
                "errored": 0,
            }

        computed = 0
        alerts = 0
        below = 0
        errored = 0

        for cluster in pending:
            try:
                score, components = await self._score_cluster(cluster)
                if score is None:
                    continue
                computed += 1
                if score >= ALERT_THRESHOLD:
                    explanation = self._build_explanation(cluster, components)
                    await self._persist_alert(
                        cluster.id, score, components, explanation
                    )
                    await self.session.commit()
                    alerts += 1
                else:
                    below += 1
            except Exception as exc:
                await self.session.rollback()
                logger.warning("scoring_iter_error", cluster_id=cluster.id, error=str(exc))
                errored += 1

        logger.info(
            "scoring_run_complete",
            computed=computed,
            alerts_generated=alerts,
            below_threshold=below,
            errored=errored,
        )
        return {
            "computed": computed,
            "alerts_generated": alerts,
            "below_threshold": below,
            "errored": errored,
        }

    async def _fetch_pending(self, limit: int) -> list[EventCluster]:
        # Cluster classificati con expectation, senza alert
        result = await self.session.execute(
            select(EventCluster)
            .join(Expectation, Expectation.cluster_id == EventCluster.id)
            .outerjoin(Alert, Alert.cluster_id == EventCluster.id)
            .where(Alert.id.is_(None))
            .where(EventCluster.event_type != "unclassified")
            .order_by(EventCluster.first_seen.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _score_cluster(
        self, cluster: EventCluster
    ) -> tuple[float | None, dict]:
        # Component: novelty
        novelty = cluster.novelty_score or 0.5

        # Component: surprise (combine direction + magnitude)
        exp = (
            await self.session.execute(
                select(Expectation).where(Expectation.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()
        if exp is None:
            return None, {}
        surprise_score = SURPRISE_MAGNITUDE_MAP.get(
            exp.surprise_magnitude, 0.3
        ) * SURPRISE_DIRECTION_MAP.get(exp.surprise_direction, 0.5)

        # Component: max exposure weight
        max_exposure = (
            await self.session.execute(
                select(func.max(Exposure.weight)).where(Exposure.cluster_id == cluster.id)
            )
        ).scalar()
        exposure_score = float(max_exposure) if max_exposure is not None else 0.0

        # Component: market confirmation (best signal di tutte le reactions)
        confirmation_rows = (
            await self.session.execute(
                select(MarketReaction.market_confirmation).where(
                    MarketReaction.cluster_id == cluster.id
                )
            )
        ).scalars().all()
        if confirmation_rows:
            confirmation_score = max(
                CONFIRMATION_MAP.get(c, 0.5) for c in confirmation_rows if c
            ) if any(c for c in confirmation_rows) else 0.5
        else:
            # Pre-event (no market reaction yet) → use 0.5 placeholder
            confirmation_score = 0.5

        # Component: source quality (best fonte fra raw_events del cluster)
        source_qualities = (
            await self.session.execute(
                select(RawEvent.source_quality)
                .where(RawEvent.cluster_id == cluster.id)
                .order_by(desc(RawEvent.published_at))
            )
        ).scalars().all()
        source_score = max(
            (SOURCE_QUALITY_MAP.get(sq, 0.5) for sq in source_qualities),
            default=0.5,
        )

        # Confounder penalty
        max_confounder = (
            await self.session.execute(
                select(func.max(Confounder.materiality_score)).where(
                    Confounder.cluster_id == cluster.id
                )
            )
        ).scalar()
        confounder_penalty = (
            min(0.5, float(max_confounder)) if max_confounder is not None else 0.0
        )

        # Combina
        base = (
            WEIGHTS["novelty"] * novelty
            + WEIGHTS["surprise"] * surprise_score
            + WEIGHTS["exposure"] * exposure_score
            + WEIGHTS["confirm"] * confirmation_score
            + WEIGHTS["source"] * source_score
        )
        impact = base * (1 - confounder_penalty)

        components = {
            "novelty": round(novelty, 3),
            "surprise": round(surprise_score, 3),
            "exposure_max": round(exposure_score, 3),
            "market_confirmation": round(confirmation_score, 3),
            "source_quality": round(source_score, 3),
            "confounder_penalty": round(confounder_penalty, 3),
            "base_score": round(base, 3),
            "impact_score": round(impact, 3),
            "surprise_direction": exp.surprise_direction,
            "surprise_magnitude": exp.surprise_magnitude,
        }
        return round(impact, 3), components

    @staticmethod
    def _build_explanation(cluster: EventCluster, components: dict) -> str:
        sd = components.get("surprise_direction", "—")
        sm = components.get("surprise_magnitude", "—")
        score = components.get("impact_score", 0.0)
        parts = [
            f"**{cluster.headline_canonical}**",
            "",
            f"Impact score: **{score}** (soglia {ALERT_THRESHOLD})",
            "",
            f"- Event type: `{cluster.event_type}`",
            f"- Surprise: {sd} / {sm}",
            f"- Novelty: {components['novelty']}",
            f"- Max exposure weight: {components['exposure_max']}",
            f"- Market confirmation: {components['market_confirmation']}",
            f"- Source quality: {components['source_quality']}",
        ]
        if components["confounder_penalty"] > 0:
            parts.append(f"- ⚠️ Confounder penalty: -{components['confounder_penalty']}")
        return "\n".join(parts)

    async def _persist_alert(
        self,
        cluster_id: int,
        score: float,
        components: dict,
        explanation: str,
    ) -> None:
        confidence = min(1.0, score)
        stmt = (
            insert(Alert)
            .values(
                cluster_id=cluster_id,
                impact_score=score,
                confidence=confidence,
                explanation_md=explanation,
                components=components,
            )
            .on_conflict_do_update(
                index_elements=["cluster_id"],
                set_={
                    "impact_score": score,
                    "confidence": confidence,
                    "explanation_md": explanation,
                    "components": components,
                },
            )
        )
        await self.session.execute(stmt)
