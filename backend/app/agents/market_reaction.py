"""Market reaction engine — calcola abnormal return e volume z-score per ogni exposure.

Per ogni (cluster_id, asset_ticker) presente in `exposures`, calcola:
- pre_event_price: ultimo close prima del cluster.first_seen
- price_15m, _1h, _1d, _3d: prezzi dopo l'evento (con i nostri daily bars
  approssimiamo: 1d = close successivo, 3d = +3 trading days)
- abnormal_return_1d/3d: (ret_ticker - beta * ret_spy) * 100
- volume_zscore: (volume_t - avg_20d_volume) / std_20d_volume
- peer_avg_ar: media abnormal_return dei peer ticker dello stesso cluster
- market_confirmation: "did_react" | "did_not_react" | "unclear"

Senza intraday Polygon Starter, i price_15m e _1h restano None (placeholder
per quando upgraderemo a Developer).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import and_, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import EventCluster, Exposure
from app.models.market import MarketReaction, Price

SPY_TICKER = "SPY"
BETA_LOOKBACK_DAYS = 60
VOLUME_BASELINE_DAYS = 20
SIGNIFICANT_AR_THRESHOLD = 0.015  # 1.5% abnormal return = "did react"
SIGNIFICANT_VOL_Z_THRESHOLD = 1.5  # 1.5 sigma volume = "did react"


class MarketReactionEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_pending(self, limit: int = 100) -> dict[str, int]:
        """Calcola reaction per cluster con exposures ma senza market_reactions."""
        pending = await self._fetch_pending(limit)
        if not pending:
            return {"computed": 0, "errored": 0, "rows": 0}

        computed = 0
        errored = 0
        rows_total = 0

        for cluster in pending:
            try:
                rows = await self._compute_for_cluster(cluster)
                if rows:
                    await self._persist(cluster.id, rows)
                    await self.session.commit()
                    rows_total += len(rows)
                    computed += 1
            except Exception as exc:
                await self.session.rollback()
                logger.warning(
                    "market_reaction_iter_error", cluster_id=cluster.id, error=str(exc)
                )
                errored += 1

        logger.info(
            "market_reaction_run_complete",
            computed=computed,
            errored=errored,
            rows=rows_total,
        )
        return {"computed": computed, "errored": errored, "rows": rows_total}

    async def _fetch_pending(self, limit: int) -> list[EventCluster]:
        # Cluster che hanno almeno una row in exposures ma nessuna in market_reactions
        result = await self.session.execute(
            select(EventCluster)
            .join(Exposure, Exposure.cluster_id == EventCluster.id)
            .outerjoin(MarketReaction, MarketReaction.cluster_id == EventCluster.id)
            .where(MarketReaction.id.is_(None))
            .group_by(EventCluster.id)
            .order_by(EventCluster.first_seen.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _compute_for_cluster(self, cluster: EventCluster) -> list[dict]:
        # Pre-compute SPY returns once per cluster
        event_dt = cluster.first_seen
        spy_returns = await self._fetch_returns(SPY_TICKER, event_dt)
        if spy_returns is None:
            return []  # Senza SPY non possiamo calcolare AR

        # Beta lookback rolling SPY (proxy market model)
        # Per semplicità in MVP usiamo beta=1.0 per tutti (mean-zero AR approximation).
        # In future si può stimare beta da OLS su 60 giorni.

        exposures = (
            await self.session.execute(
                select(Exposure).where(Exposure.cluster_id == cluster.id)
            )
        ).scalars().all()

        # Calcola tutte le AR
        ticker_to_ar: dict[str, tuple[float | None, float | None]] = {}
        rows: list[dict] = []

        for exposure in exposures:
            ticker = exposure.asset_ticker
            returns = await self._fetch_returns(ticker, event_dt)
            if returns is None:
                continue

            beta = 1.0  # MVP semplice
            ar_1d = self._abnormal_return(returns.ret_1d, spy_returns.ret_1d, beta)
            ar_3d = self._abnormal_return(returns.ret_3d, spy_returns.ret_3d, beta)
            ticker_to_ar[ticker] = (ar_1d, ar_3d)

            vol_z = await self._volume_zscore(ticker, event_dt)
            confirmation = self._classify_confirmation(ar_1d, vol_z)

            rows.append(
                {
                    "ticker": ticker,
                    "pre_event_price": returns.pre_close,
                    "price_15m": None,
                    "price_1h": None,
                    "price_1d": returns.close_1d,
                    "price_3d": returns.close_3d,
                    "abnormal_return_1d": ar_1d,
                    "abnormal_return_3d": ar_3d,
                    "volume_zscore": vol_z,
                    "peer_avg_ar": None,  # placeholder, riempito dopo
                    "market_confirmation": confirmation,
                }
            )

        # Calcola peer_avg_ar usando le AR dei ticker classificati come peer/etf/sector
        peer_exposure_types = {"peer", "etf", "sector"}
        peer_tickers = {
            e.asset_ticker for e in exposures if e.exposure_type in peer_exposure_types
        }
        peer_ar_values = [
            ticker_to_ar[t][0]
            for t in peer_tickers
            if ticker_to_ar.get(t) and ticker_to_ar[t][0] is not None
        ]
        peer_avg = (
            sum(peer_ar_values) / len(peer_ar_values) if peer_ar_values else None
        )
        for row in rows:
            row["peer_avg_ar"] = peer_avg

        return rows

    async def _fetch_returns(
        self, ticker: str, event_dt: datetime
    ) -> TickerReturns | None:
        """Pre-event close, +1d close, +3d close, return % per ciascuno."""
        # Pre-event close = ultimo close < event_dt
        pre = (
            await self.session.execute(
                select(Price.close, Price.ts)
                .where(Price.ticker == ticker)
                .where(Price.ts < event_dt)
                .order_by(desc(Price.ts))
                .limit(1)
            )
        ).first()
        if pre is None:
            return None
        pre_close, _pre_ts = pre

        # 1d successivo = primo close > event_dt
        d1 = (
            await self.session.execute(
                select(Price.close, Price.ts)
                .where(Price.ticker == ticker)
                .where(Price.ts >= event_dt)
                .order_by(Price.ts.asc())
                .limit(1)
            )
        ).first()
        close_1d = d1[0] if d1 else None

        # 3d successivo = 3° close > event_dt
        d3_rows = (
            await self.session.execute(
                select(Price.close)
                .where(Price.ticker == ticker)
                .where(Price.ts >= event_dt)
                .order_by(Price.ts.asc())
                .limit(3)
            )
        ).all()
        close_3d = d3_rows[-1][0] if len(d3_rows) >= 3 else None

        ret_1d = (close_1d - pre_close) / pre_close if close_1d and pre_close else None
        ret_3d = (close_3d - pre_close) / pre_close if close_3d and pre_close else None

        return TickerReturns(
            pre_close=pre_close,
            close_1d=close_1d,
            close_3d=close_3d,
            ret_1d=ret_1d,
            ret_3d=ret_3d,
        )

    async def _volume_zscore(self, ticker: str, event_dt: datetime) -> float | None:
        """Z-score del volume del primo trading day post-evento vs media 20 giorni precedenti."""
        post_volume_row = (
            await self.session.execute(
                select(Price.volume)
                .where(Price.ticker == ticker)
                .where(Price.ts >= event_dt)
                .order_by(Price.ts.asc())
                .limit(1)
            )
        ).first()
        if post_volume_row is None:
            return None
        post_volume = float(post_volume_row[0])

        cutoff = event_dt - timedelta(days=VOLUME_BASELINE_DAYS + 5)
        stats_row = (
            await self.session.execute(
                select(
                    func.avg(Price.volume).label("avg"),
                    func.stddev_samp(Price.volume).label("std"),
                )
                .where(Price.ticker == ticker)
                .where(and_(Price.ts >= cutoff, Price.ts < event_dt))
            )
        ).first()
        if stats_row is None or stats_row[0] is None or stats_row[1] is None:
            return None
        avg = float(stats_row[0])
        std = float(stats_row[1])
        if std == 0:
            return None
        return (post_volume - avg) / std

    @staticmethod
    def _abnormal_return(
        ret_ticker: float | None, ret_market: float | None, beta: float
    ) -> float | None:
        if ret_ticker is None or ret_market is None:
            return None
        return ret_ticker - beta * ret_market

    @staticmethod
    def _classify_confirmation(
        ar_1d: float | None, volume_z: float | None
    ) -> str | None:
        if ar_1d is None:
            return None
        ar_abs = abs(ar_1d)
        vol_strong = (volume_z or 0) >= SIGNIFICANT_VOL_Z_THRESHOLD
        if ar_abs >= SIGNIFICANT_AR_THRESHOLD and vol_strong:
            return "did_react"
        if ar_abs < SIGNIFICANT_AR_THRESHOLD / 2 and not vol_strong:
            return "did_not_react"
        return "unclear"

    async def _persist(self, cluster_id: int, rows: list[dict]) -> None:
        for row in rows:
            ticker = row.pop("ticker")
            stmt = (
                insert(MarketReaction)
                .values(cluster_id=cluster_id, ticker=ticker, **row)
                .on_conflict_do_update(
                    constraint="uq_reaction_cluster_ticker",
                    set_={k: v for k, v in row.items()},
                )
            )
            await self.session.execute(stmt)


class TickerReturns:
    __slots__ = ("close_1d", "close_3d", "pre_close", "ret_1d", "ret_3d")

    def __init__(
        self,
        pre_close: float,
        close_1d: float | None,
        close_3d: float | None,
        ret_1d: float | None,
        ret_3d: float | None,
    ) -> None:
        self.pre_close = pre_close
        self.close_1d = close_1d
        self.close_3d = close_3d
        self.ret_1d = ret_1d
        self.ret_3d = ret_3d
