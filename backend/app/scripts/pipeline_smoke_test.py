"""Smoke test della pipeline Phase 4-8 senza dipendere dal classifier LLM.

Strategia:
1. Trova un raw_event finnhub:earnings_calendar per AAPL (ticker presente
   nell'universe + entity graph seedato)
2. Lo setta come primary entity del suo cluster + event_type='earnings'
3. Esegue: expectation → exposure → market_reaction → confounder → scoring
4. Verifica le tabelle popolate

Idempotente: se la classificazione manuale è già fatta, semplicemente esegue
gli agenti su quel cluster + altri eventualmente classificati.

Uso: uv run python -m app.scripts.pipeline_smoke_test
"""

from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy import desc, select, update
from sqlalchemy.dialects.postgresql import insert

from app.agents.confounder import ConfounderDetector
from app.agents.exposure import ExposureEngine
from app.agents.market_reaction import MarketReactionEngine
from app.agents.outcome_tracker import OutcomeTracker
from app.agents.scoring import ScoringEngine
from app.core.db import SessionLocal
from app.models.entities import Entity
from app.models.events import EventCluster, EventEntity, RawEvent

TARGET_TICKER = "NVDA"


async def main() -> int:
    async with SessionLocal() as session:
        # 1. Trova un raw_event finnhub:earnings_calendar per AAPL
        raw = (
            await session.execute(
                select(RawEvent)
                .where(RawEvent.source == "finnhub:earnings_calendar")
                .where(RawEvent.headline.like(f"{TARGET_TICKER}%"))
                .order_by(desc(RawEvent.published_at))
                .limit(1)
            )
        ).scalar_one_or_none()

        if raw is None or raw.cluster_id is None:
            print(f"Nessun raw_event earnings_calendar per {TARGET_TICKER} trovato in DB.")
            return 1

        cluster_id = raw.cluster_id
        print(f"Trovato raw_event #{raw.id} → cluster #{cluster_id}")
        print(f"  Headline: {raw.headline}")
        print(f"  Meta: {raw.raw_meta}")

        # 2. Setta cluster.event_type='earnings' + assicura entity AAPL come primary
        await session.execute(
            update(EventCluster)
            .where(EventCluster.id == cluster_id)
            .values(event_type="earnings", summary=raw.headline)
        )

        entity = (
            await session.execute(select(Entity).where(Entity.ticker == TARGET_TICKER))
        ).scalar_one_or_none()
        if entity is None:
            print(f"Entity {TARGET_TICKER} non trovata, dovrebbe essere già seedata!")
            return 1

        await session.execute(
            insert(EventEntity)
            .values(cluster_id=cluster_id, entity_id=entity.id, role="primary")
            .on_conflict_do_update(
                index_elements=["cluster_id", "entity_id"],
                set_={"role": "primary"},
            )
        )
        await session.commit()
        print(f"Cluster {cluster_id} classificato manualmente: event_type=earnings, primary=AAPL")

    # 3. Run pipeline agents
    async with SessionLocal() as session:
        from app.agents.expectation import ExpectationEngine

        print("\n→ Expectation engine...")
        exp_counts = await ExpectationEngine(session).process_pending(limit=10)
        print(f"  {exp_counts}")

    async with SessionLocal() as session:
        print("\n→ Exposure engine...")
        exp_counts = await ExposureEngine(session).process_pending(limit=10)
        print(f"  {exp_counts}")

    async with SessionLocal() as session:
        print("\n→ Market reaction engine...")
        mr_counts = await MarketReactionEngine(session).process_pending(limit=10)
        print(f"  {mr_counts}")

    async with SessionLocal() as session:
        print("\n→ Confounder detector...")
        cd_counts = await ConfounderDetector(session).process_pending(limit=10)
        print(f"  {cd_counts}")

    async with SessionLocal() as session:
        print("\n→ Scoring engine...")
        sc_counts = await ScoringEngine(session).process_pending(limit=10)
        print(f"  {sc_counts}")

    async with SessionLocal() as session:
        print("\n→ Outcome tracker (probabilmente niente: alert appena creato)...")
        ot_counts = await OutcomeTracker(session).process_pending(limit=10)
        print(f"  {ot_counts}")

    # 4. Riepilogo finale
    async with SessionLocal() as session:
        from sqlalchemy import func

        from app.models.alerts import Alert
        from app.models.events import Expectation, Exposure
        from app.models.market import Confounder, MarketReaction

        print("\n=== Riepilogo DB dopo smoke test ===")
        for label, model in [
            ("expectations", Expectation),
            ("exposures", Exposure),
            ("market_reactions", MarketReaction),
            ("confounders", Confounder),
            ("alerts", Alert),
        ]:
            c = (
                await session.execute(select(func.count()).select_from(model))
            ).scalar()
            print(f"  {label}: {c}")

        # Mostra l'alert creato se esiste
        alert = (
            await session.execute(
                select(Alert).order_by(desc(Alert.created_at)).limit(1)
            )
        ).scalar_one_or_none()
        if alert:
            print("\n=== Ultimo alert generato ===")
            print(f"  Cluster #{alert.cluster_id}")
            print(f"  Impact score: {alert.impact_score}")
            print(f"  Confidence: {alert.confidence}")
            print(f"  Components: {alert.components}")
            print(f"  Explanation (primi 500 char):\n  {alert.explanation_md[:500]}")

    logger.info("smoke_test_done")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
