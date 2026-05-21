"""Engine di deduplica semantica → event clustering.

Ogni raw_event nuovo viene embeddato (Voyage AI voyage-3.5-lite, 1024 dim) e
confrontato via cosine similarity con i cluster esistenti nella finestra
temporale recente. Soglia 0.85 = stesso evento; sotto = cluster nuovo.

Mantiene:
- event_clusters: una riga per evento "canonico" (prima comparsa credibile)
- event_cluster_members: link n:m fra raw_events e cluster
- raw_events.cluster_id: cache del cluster di appartenenza
"""

from __future__ import annotations

from datetime import datetime, timedelta

import voyageai
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.events import EventCluster, EventClusterMember, RawEvent

VOYAGE_MODEL = "voyage-3.5-lite"
EMBEDDING_DIM = 1024
SIMILARITY_THRESHOLD = 0.85
LOOKBACK_HOURS = 24

# Sources che usano URL sintetici deterministici (synthetic_url unico per chiave
# symbol+date). NON applichiamo dedup semantico: ogni raw_event è un cluster
# distinto. Il dedup esatto via url_hash (in base.NewsIngester) impedisce già
# duplicati cross-batch.
# Rationale: queste headline hanno format-template ("X earnings scheduled for Y")
# che la similarità coseno di embeddings considera erroneamente simili anche fra
# ticker diversi.
STRUCTURED_SOURCE_PREFIXES = ("finnhub:earnings_calendar", "fred:")


class DedupEngine:
    """Processa raw_events non clusterizzati in cluster di eventi.

    Strategia: per ogni batch di N raw_events nuovi, embeddiamo le headline
    (concatenate al body breve se presente), cerchiamo il cluster più simile
    nella finestra `LOOKBACK_HOURS`. Se similarity ≥ SIMILARITY_THRESHOLD →
    attach; altrimenti → seed di nuovo cluster.
    """

    def __init__(self, session: AsyncSession, batch_size: int = 32) -> None:
        self.session = session
        self.batch_size = batch_size
        self.api_key = get_settings().voyage_api_key
        self._client: voyageai.Client | None = None

    @property
    def client(self) -> voyageai.Client:
        if self._client is None:
            self._client = voyageai.Client(api_key=self.api_key)
        return self._client

    async def process_pending(self, limit: int = 500) -> dict[str, int]:
        """Processa fino a `limit` raw_events senza cluster_id.

        Ritorna: counts {clustered_new, clustered_existing, errored}.
        """
        if not self.api_key:
            logger.error("dedup_no_voyage_key")
            return {"clustered_new": 0, "clustered_existing": 0, "errored": 0}

        pending = await self._fetch_pending(limit)
        if not pending:
            return {"clustered_new": 0, "clustered_existing": 0, "errored": 0}

        new_count = 0
        existing_count = 0
        errored = 0

        # Split per strategia: structured sources → singolo cluster ognuno,
        # senza chiamare Voyage (no rischio falsi-positivi su template headlines).
        structured = [e for e in pending if self._is_structured(e.source)]
        semantic = [e for e in pending if not self._is_structured(e.source)]

        for event in structured:
            try:
                await self._create_cluster_no_embedding(event)
                await self.session.commit()
                new_count += 1
            except Exception as exc:
                await self.session.rollback()
                logger.warning(
                    "dedup_structured_error", raw_event_id=event.id, error=str(exc)
                )
                errored += 1

        # Per news libere: pipeline embedding + cosine similarity come prima.
        for batch_start in range(0, len(semantic), self.batch_size):
            batch = semantic[batch_start : batch_start + self.batch_size]
            texts = [self._build_text(event) for event in batch]

            try:
                embeddings = self.client.embed(
                    texts, model=VOYAGE_MODEL, input_type="document"
                ).embeddings
            except Exception as exc:
                logger.warning("voyage_embed_failed", batch_size=len(batch), error=str(exc))
                errored += len(batch)
                continue

            for event, embedding in zip(batch, embeddings, strict=True):
                try:
                    matched = await self._find_similar_cluster(
                        embedding=embedding,
                        before=event.published_at or event.ingested_at,
                    )
                    if matched is not None:
                        await self._attach_to_cluster(event, matched[0], matched[1])
                        existing_count += 1
                    else:
                        await self._create_cluster(event, embedding)
                        new_count += 1
                    # Commit granulare: ogni evento è atomico, una failure non
                    # poisona tutto il batch.
                    await self.session.commit()
                except Exception as exc:
                    await self.session.rollback()
                    logger.warning(
                        "dedup_event_error", raw_event_id=event.id, error=str(exc)
                    )
                    errored += 1

        logger.info(
            "dedup_run_complete",
            clustered_new=new_count,
            clustered_existing=existing_count,
            errored=errored,
        )
        return {
            "clustered_new": new_count,
            "clustered_existing": existing_count,
            "errored": errored,
        }

    async def _fetch_pending(self, limit: int) -> list[RawEvent]:
        result = await self.session.execute(
            select(RawEvent)
            .where(RawEvent.cluster_id.is_(None))
            .order_by(RawEvent.ingested_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _find_similar_cluster(
        self, embedding: list[float], before: datetime
    ) -> tuple[int, float] | None:
        """Trova il cluster più simile entro LOOKBACK_HOURS dal timestamp dell'evento.

        Usa pgvector cosine distance (operatore <=>). Cosine similarity = 1 - distance.
        """
        cutoff = before - timedelta(hours=LOOKBACK_HOURS)
        # pgvector: <=> = cosine distance (0=identical, 2=opposite). Convertiamo in similarity.
        result = await self.session.execute(
            select(
                EventCluster.id,
                (1 - EventCluster.embedding.cosine_distance(embedding)).label("similarity"),
            )
            .where(EventCluster.embedding.is_not(None))
            .where(EventCluster.first_seen >= cutoff)
            .order_by(EventCluster.embedding.cosine_distance(embedding))
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            return None
        cluster_id, similarity = row
        if similarity is None or float(similarity) < SIMILARITY_THRESHOLD:
            return None
        return cluster_id, float(similarity)

    async def _attach_to_cluster(
        self, event: RawEvent, cluster_id: int, similarity: float
    ) -> None:
        self.session.add(
            EventClusterMember(
                cluster_id=cluster_id, raw_event_id=event.id, similarity=similarity
            )
        )
        await self.session.execute(
            update(RawEvent).where(RawEvent.id == event.id).values(cluster_id=cluster_id)
        )

    async def _create_cluster(self, event: RawEvent, embedding: list[float]) -> None:
        cluster = EventCluster(
            first_seen=event.published_at or event.ingested_at,
            event_type="unclassified",  # sarà valorizzato dal classifier in Fase 2
            headline_canonical=event.headline,
            summary=event.body,
            embedding=embedding,
            novelty_score=0.5,
        )
        self.session.add(cluster)
        await self.session.flush()

        self.session.add(
            EventClusterMember(cluster_id=cluster.id, raw_event_id=event.id, similarity=1.0)
        )
        await self.session.execute(
            update(RawEvent).where(RawEvent.id == event.id).values(cluster_id=cluster.id)
        )

    @staticmethod
    def _is_structured(source: str) -> bool:
        return any(source.startswith(p) for p in STRUCTURED_SOURCE_PREFIXES)

    async def _create_cluster_no_embedding(self, event: RawEvent) -> None:
        """Cluster diretto senza embedding per fonti structured (earnings_calendar, fred).

        Un raw_event = un cluster. Niente similarity check (gli URL sintetici
        deterministici fanno già il lavoro di dedup esatto tramite url_hash).
        """
        cluster = EventCluster(
            first_seen=event.published_at or event.ingested_at,
            event_type="unclassified",
            headline_canonical=event.headline,
            summary=event.body,
            embedding=None,
            novelty_score=0.5,
        )
        self.session.add(cluster)
        await self.session.flush()

        self.session.add(
            EventClusterMember(cluster_id=cluster.id, raw_event_id=event.id, similarity=1.0)
        )
        from sqlalchemy import update

        await self.session.execute(
            update(RawEvent).where(RawEvent.id == event.id).values(cluster_id=cluster.id)
        )

    @staticmethod
    def _build_text(event: RawEvent) -> str:
        """Costruisce il testo da embeddare. Headline + primi 300 char del body."""
        text = event.headline.strip()
        if event.body:
            body_clip = event.body.strip()[:300]
            if body_clip and body_clip != text:
                text = f"{text}. {body_clip}"
        return text
