"""Pulisce i cluster contaminati che contengono raw_events da fonti structured.

Pre-fix il dedup engine raggruppava earnings_calendar di ticker diversi insieme
(headline template-simili). Dopo il fix, le fonti structured ottengono 1 cluster
per raw_event. Per applicare il fix retroattivamente:

1. Trova cluster con almeno 1 raw_event da finnhub:earnings_calendar o fred:*
2. Marca questi cluster per cancellazione (cascade su event_cluster_members + event_entities)
3. Reset raw_events.cluster_id = NULL per quegli eventi → il dedup li riprocesserà
   correttamente al prossimo run (creando 1 cluster per raw_event grazie al fix)

Idempotente: rieseguibile senza danni.

Uso:
    uv run python -m app.scripts.cleanup_structured_clusters
    uv run python -m app.scripts.cleanup_structured_clusters --dry-run
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.ingestion.dedup import STRUCTURED_SOURCE_PREFIXES
from app.models.alerts import Alert, Outcome
from app.models.events import (
    EventCluster,
    EventClusterMember,
    EventEntity,
    Expectation,
    Exposure,
    RawEvent,
)
from app.models.market import Confounder, MarketReaction


async def find_contaminated_clusters(session: AsyncSession) -> list[int]:
    """Cluster con almeno 1 raw_event da fonti structured."""
    or_clauses = [RawEvent.source.like(f"{p}%") for p in STRUCTURED_SOURCE_PREFIXES]
    from sqlalchemy import or_

    result = await session.execute(
        select(EventCluster.id)
        .join(RawEvent, RawEvent.cluster_id == EventCluster.id)
        .where(or_(*or_clauses))
        .distinct()
    )
    return list(result.scalars().all())


async def main(dry_run: bool) -> int:
    async with SessionLocal() as session:
        cluster_ids = await find_contaminated_clusters(session)

        if not cluster_ids:
            print("Nessun cluster contaminato. Niente da fare.")
            return 0

        print(f"Trovati {len(cluster_ids)} cluster contaminati da fonti structured.")

        if dry_run:
            print("DRY RUN — niente cancellato.")
            sample = cluster_ids[:5]
            print(f"Sample IDs: {sample}")
            return 0

        # 1. Reset cluster_id sui raw_events di quei cluster
        await session.execute(
            update(RawEvent)
            .where(RawEvent.cluster_id.in_(cluster_ids))
            .values(cluster_id=None)
        )

        # 2. Cancella le righe figlie (alcune hanno cascade, esplicito per chiarezza)
        # Outcome → Alert → Confounder/Exposure/Expectation/MarketReaction/EventEntity/Member → Cluster
        await session.execute(
            delete(Outcome).where(
                Outcome.alert_id.in_(
                    select(Alert.id).where(Alert.cluster_id.in_(cluster_ids))
                )
            )
        )
        await session.execute(delete(Alert).where(Alert.cluster_id.in_(cluster_ids)))
        await session.execute(
            delete(Confounder).where(Confounder.cluster_id.in_(cluster_ids))
        )
        await session.execute(
            delete(MarketReaction).where(MarketReaction.cluster_id.in_(cluster_ids))
        )
        await session.execute(
            delete(Exposure).where(Exposure.cluster_id.in_(cluster_ids))
        )
        await session.execute(
            delete(Expectation).where(Expectation.cluster_id.in_(cluster_ids))
        )
        await session.execute(
            delete(EventEntity).where(EventEntity.cluster_id.in_(cluster_ids))
        )
        await session.execute(
            delete(EventClusterMember).where(EventClusterMember.cluster_id.in_(cluster_ids))
        )

        # 3. Cancella i cluster
        await session.execute(
            delete(EventCluster).where(EventCluster.id.in_(cluster_ids))
        )

        await session.commit()
        logger.info("cleanup_done", clusters_removed=len(cluster_ids))
        print(f"Cancellati {len(cluster_ids)} cluster contaminati.")
        print("I raw_events sono tornati cluster_id=NULL e verranno ri-clusterizzati")
        print("dal prossimo run del DedupEngine (1 cluster per ticker/date).")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
