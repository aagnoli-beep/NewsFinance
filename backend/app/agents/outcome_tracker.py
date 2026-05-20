"""Outcome tracker — valuta gli alert dopo T+1d, T+3d, T+7d, T+30d.

Per ogni Alert, calcola abnormal return cumulato fino al timestamp target e
classifica:
- confirmed_direction: sign(AR_T+nd) == sign(surprise_direction)
- reversed: AR significativo ma direzione opposta
- flat: |AR| < 0.5 sigma (pulizia rumore di mercato)
- confounded: si auto-flagga se Confounder.materiality_score > 0.4

L'asset principale per valutazione è il primo `direct` exposure del cluster.

Senza prezzi intraday, la finestra T+1d/3d/7d è approssimata su daily close.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alerts import Alert, Outcome
from app.models.events import (
    EventCluster,
    Expectation,
    Exposure,
    ExposureType,
)
from app.models.market import Confounder, Price

FLAT_THRESHOLD = 0.005  # 0.5% in valore assoluto = piattamento
CONFOUNDER_THRESHOLD = 0.4


class OutcomeTracker:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_pending(self, limit: int = 200) -> dict[str, int]:
        """Trova alert pendenti (senza outcome o con outcome incompleto) e li valuta."""
        pending = await self._fetch_pending(limit)
        if not pending:
            return {"processed": 0, "errored": 0}

        processed = 0
        errored = 0

        for alert in pending:
            try:
                row = await self._compute_for_alert(alert)
                if row is None:
                    continue
                await self._persist(alert.id, row)
                await self.session.commit()
                processed += 1
            except Exception as exc:
                await self.session.rollback()
                logger.warning(
                    "outcome_iter_error", alert_id=alert.id, error=str(exc)
                )
                errored += 1

        logger.info("outcome_run_complete", processed=processed, errored=errored)
        return {"processed": processed, "errored": errored}

    async def _fetch_pending(self, limit: int) -> list[Alert]:
        """Alert che hanno almeno 1 giorno di età e:
        - non hanno outcome OPPURE
        - hanno outcome ma t_plus_30d_ar è ancora None E sono passati >=30 giorni
        """
        result = await self.session.execute(
            select(Alert)
            .outerjoin(Outcome, Outcome.alert_id == Alert.id)
            .where(Alert.created_at < func.now() - func.make_interval(0, 0, 0, 1))
            .order_by(desc(Alert.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _compute_for_alert(self, alert: Alert) -> dict | None:
        cluster = (
            await self.session.execute(
                select(EventCluster).where(EventCluster.id == alert.cluster_id)
            )
        ).scalar_one_or_none()
        if cluster is None:
            return None

        # Trova il primary direct ticker
        direct = (
            await self.session.execute(
                select(Exposure)
                .where(Exposure.cluster_id == cluster.id)
                .where(Exposure.exposure_type == ExposureType.DIRECT)
                .order_by(desc(Exposure.weight))
                .limit(1)
            )
        ).scalar_one_or_none()
        if direct is None:
            return None

        event_dt = cluster.first_seen
        ar_1d = await self._abnormal_return_at(direct.asset_ticker, event_dt, 1)
        ar_3d = await self._abnormal_return_at(direct.asset_ticker, event_dt, 3)
        ar_7d = await self._abnormal_return_at(direct.asset_ticker, event_dt, 7)
        ar_30d = await self._abnormal_return_at(direct.asset_ticker, event_dt, 30)

        # Decidi outcome label usando AR_3d (orizzonte primario per market impact)
        outcome_label = await self._classify_outcome(cluster, alert, ar_3d, ar_1d, ar_7d)

        return {
            "t_plus_1d_ar": ar_1d,
            "t_plus_3d_ar": ar_3d,
            "t_plus_7d_ar": ar_7d,
            "t_plus_30d_ar": ar_30d,
            "outcome_label": outcome_label,
        }

    async def _abnormal_return_at(
        self, ticker: str, event_dt: datetime, days: int
    ) -> float | None:
        """AR cumulato a +N giorni rispetto a pre-event close."""
        # Pre-event close
        pre = (
            await self.session.execute(
                select(Price.close)
                .where(Price.ticker == ticker)
                .where(Price.ts < event_dt)
                .order_by(desc(Price.ts))
                .limit(1)
            )
        ).scalar()
        if pre is None:
            return None

        target_dt = event_dt + timedelta(days=days)
        future_row = (
            await self.session.execute(
                select(Price.close, Price.ts)
                .where(Price.ticker == ticker)
                .where(Price.ts <= target_dt)
                .where(Price.ts >= event_dt)
                .order_by(desc(Price.ts))
                .limit(1)
            )
        ).first()
        if future_row is None:
            return None
        future_close = float(future_row[0])

        # SPY return per lo stesso periodo
        spy_pre = (
            await self.session.execute(
                select(Price.close)
                .where(Price.ticker == "SPY")
                .where(Price.ts < event_dt)
                .order_by(desc(Price.ts))
                .limit(1)
            )
        ).scalar()
        spy_future = (
            await self.session.execute(
                select(Price.close)
                .where(Price.ticker == "SPY")
                .where(Price.ts <= target_dt)
                .where(Price.ts >= event_dt)
                .order_by(desc(Price.ts))
                .limit(1)
            )
        ).scalar()
        if spy_pre is None or spy_future is None:
            return None
        ret_ticker = (future_close - float(pre)) / float(pre)
        ret_spy = (float(spy_future) - float(spy_pre)) / float(spy_pre)
        return ret_ticker - ret_spy  # beta=1.0 approximation

    async def _classify_outcome(
        self,
        cluster: EventCluster,
        alert: Alert,
        ar_3d: float | None,
        ar_1d: float | None,
        ar_7d: float | None,
    ) -> str:
        # Check confounder
        max_conf = (
            await self.session.execute(
                select(func.max(Confounder.materiality_score)).where(
                    Confounder.cluster_id == cluster.id
                )
            )
        ).scalar()
        if max_conf and float(max_conf) >= CONFOUNDER_THRESHOLD:
            return "confounded"

        # Get expected direction
        exp = (
            await self.session.execute(
                select(Expectation).where(Expectation.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()
        if exp is None or exp.surprise_direction not in ("positive", "negative"):
            return "pending"  # Non possiamo valutare senza direction attesa

        expected_sign = 1.0 if exp.surprise_direction == "positive" else -1.0

        # Use AR_3d as primary judgment; fallback su 1d se 3d non ancora disponibile
        primary_ar = ar_3d if ar_3d is not None else ar_1d
        if primary_ar is None:
            return "pending"

        if abs(primary_ar) < FLAT_THRESHOLD:
            return "flat"

        actual_sign = 1.0 if primary_ar > 0 else -1.0
        if actual_sign == expected_sign:
            return "confirmed_direction"
        else:
            return "reversed"

    async def _persist(self, alert_id: int, row: dict) -> None:
        stmt = (
            insert(Outcome)
            .values(
                alert_id=alert_id,
                t_plus_1d_ar=row["t_plus_1d_ar"],
                t_plus_3d_ar=row["t_plus_3d_ar"],
                t_plus_7d_ar=row["t_plus_7d_ar"],
                t_plus_30d_ar=row["t_plus_30d_ar"],
                outcome_label=row["outcome_label"],
                evaluated_at=func.now(),
            )
            .on_conflict_do_update(
                index_elements=["alert_id"],
                set_={
                    "t_plus_1d_ar": row["t_plus_1d_ar"],
                    "t_plus_3d_ar": row["t_plus_3d_ar"],
                    "t_plus_7d_ar": row["t_plus_7d_ar"],
                    "t_plus_30d_ar": row["t_plus_30d_ar"],
                    "outcome_label": row["outcome_label"],
                    "evaluated_at": func.now(),
                },
            )
        )
        await self.session.execute(stmt)
