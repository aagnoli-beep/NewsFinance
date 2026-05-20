"""Confounder detection — trova altri eventi nello stesso intervallo che potrebbero
confondere l'attribuzione causale.

Algoritmo:
1. Per ogni cluster classificato, cerca altri cluster nei ±24h
2. Filtra a cluster che condividono almeno una primary entity, oppure
   appartengono a categorie macro (central_bank, macro_data) di rilevanza ampia
3. Per ogni candidato calcola materiality_score basato su:
   - sovrapposizione entità primary
   - novelty_score del confounder
   - tipo evento (FOMC/CPI hanno materiality 1.0 per default)

Output: row in `confounders` con (cluster_id, confounding_cluster_id, materiality).
"""

from __future__ import annotations

from datetime import timedelta

from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import EventCluster, EventEntity
from app.models.market import Confounder

LOOKBACK_HOURS = 24

# Event type che hanno materiality alta per default (impattano molti asset)
SYSTEMIC_TYPES = {"central_bank", "macro_data", "geopolitical"}


class ConfounderDetector:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_pending(self, limit: int = 100) -> dict[str, int]:
        """Per ogni cluster classificato senza confounder calcolati, scan ±24h."""
        pending = await self._fetch_pending(limit)
        if not pending:
            return {"processed": 0, "confounders_total": 0, "errored": 0}

        processed = 0
        total = 0
        errored = 0

        for cluster in pending:
            try:
                pairs = await self._compute_for_cluster(cluster)
                if pairs:
                    await self._persist(pairs)
                    await self.session.commit()
                    total += len(pairs)
                processed += 1
            except Exception as exc:
                await self.session.rollback()
                logger.warning(
                    "confounder_iter_error", cluster_id=cluster.id, error=str(exc)
                )
                errored += 1

        logger.info(
            "confounder_run_complete",
            processed=processed,
            confounders=total,
            errored=errored,
        )
        return {"processed": processed, "confounders_total": total, "errored": errored}

    async def _fetch_pending(self, limit: int) -> list[EventCluster]:
        """Cluster classificati che non sono ancora stati scannati per confounder.

        Per semplicità: cluster classificati che non figurano come `cluster_id` in
        nessuna row di `confounders`. Significa che il batch potrebbe ricalcolare
        confounder se aggiungiamo cluster nuovi nello stesso intervallo — accettabile.
        """
        result = await self.session.execute(
            select(EventCluster)
            .outerjoin(Confounder, Confounder.cluster_id == EventCluster.id)
            .where(EventCluster.event_type != "unclassified")
            .where(Confounder.id.is_(None))
            .order_by(EventCluster.first_seen.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _compute_for_cluster(
        self, cluster: EventCluster
    ) -> list[tuple[int, int, float, str]]:
        """Restituisce list di tuple: (cluster_id, confounding_cluster_id, materiality, rationale)."""
        # Window ±24h
        start = cluster.first_seen - timedelta(hours=LOOKBACK_HOURS)
        end = cluster.first_seen + timedelta(hours=LOOKBACK_HOURS)

        # Primary entities del cluster di interesse
        primary_q = (
            select(EventEntity.entity_id)
            .where(EventEntity.cluster_id == cluster.id)
            .where(EventEntity.role == "primary")
        )
        primary_ids = list((await self.session.execute(primary_q)).scalars().all())

        # Candidati: cluster nella finestra, classificati, diversi
        candidates_q = (
            select(EventCluster)
            .where(EventCluster.id != cluster.id)
            .where(EventCluster.event_type != "unclassified")
            .where(and_(EventCluster.first_seen >= start, EventCluster.first_seen <= end))
        )
        candidates = list((await self.session.execute(candidates_q)).scalars().all())

        confounders: list[tuple[int, int, float, str]] = []
        for cand in candidates:
            # Sovrapposizione entità primary
            cand_primary_q = (
                select(EventEntity.entity_id)
                .where(EventEntity.cluster_id == cand.id)
                .where(EventEntity.role == "primary")
            )
            cand_primary_ids = set(
                (await self.session.execute(cand_primary_q)).scalars().all()
            )
            shared = set(primary_ids) & cand_primary_ids

            is_systemic = cand.event_type in SYSTEMIC_TYPES
            if not shared and not is_systemic:
                continue

            # Calcolo materiality
            score = 0.0
            rationales: list[str] = []
            if shared:
                score += 0.5 + 0.1 * min(len(shared), 5)
                rationales.append(f"shared_primary_entities={len(shared)}")
            if is_systemic:
                score = max(score, 0.7)
                rationales.append(f"systemic_event_type={cand.event_type}")

            score = min(score, 1.0) * (cand.novelty_score or 0.5)
            if score < 0.1:
                continue

            confounders.append(
                (
                    cluster.id,
                    cand.id,
                    round(score, 3),
                    "; ".join(rationales),
                )
            )
        return confounders

    async def _persist(self, pairs: list[tuple[int, int, float, str]]) -> None:
        for cid, ccid, score, rationale in pairs:
            stmt = (
                insert(Confounder)
                .values(
                    cluster_id=cid,
                    confounding_cluster_id=ccid,
                    materiality_score=score,
                    rationale=rationale,
                )
                .on_conflict_do_update(
                    constraint="uq_confounder_pair",
                    set_={"materiality_score": score, "rationale": rationale},
                )
            )
            await self.session.execute(stmt)
