"""Event classifier — assegna event_type, entities, novelty, summary a un cluster.

Usa Claude Haiku 4.5 con structured output (tool_use). System prompt cachato
con prompt caching ephemeral (riduce costo del 90% sui token ripetuti).

Input:  testo headline+body del cluster e dei suoi raw_events
Output: ClassifiedEvent (Pydantic) → scritto su event_clusters + event_entities
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import anthropic
from loguru import logger
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.entity_linker import link_entities
from app.agents.schemas import EVENT_TYPE_VALUES, ClassifiedEvent
from app.core.config import get_settings
from app.core.llm import HAIKU_MODEL, cacheable_system, get_anthropic_client
from app.models.events import EventCluster, RawEvent

SYSTEM_PROMPT = """Sei un classificatore di eventi finanziari per un sistema di market-impact intelligence.

Il tuo compito: data una notizia (headline + body breve), classificarla rispetto a:
1) event_type — tipo di evento (vedi enum nello schema)
2) entities — entità rilevanti (aziende quotate, persone chiave, paesi, commodity, central bank, ETF, settori)
3) sentiment — semplice positive/negative/neutral basato sul testo, NON sul prezzo
4) novelty_score — quanto è materiale e originale (0=routine come weekly buyback report, 1=evento maggiore inatteso)
5) summary — una frase neutra che descrive cosa è successo
6) confidence — quanto sei sicuro della classificazione

Regole importanti:
- Per "entities" estrai SOLO entità nominate o chiaramente implicite, max 12.
- Se è una company quotata su mercati USA, compila "ticker" (es. AAPL, MSFT, NVDA, SPY).
  Se ETF noto compila ticker (es. XLE, GLD). Altrimenti lascia ticker=null.
- role=primary se l'evento è SU quell'entità; role=mentioned se è citata di passaggio.
- event_type "macro_data" per CPI/NFP/PMI/GDP/UNRATE; "central_bank" per FOMC/ECB rate decisions.
- event_type "earnings" per quarterly/annual earnings reports (sia beat che miss).
- event_type "guidance" per outlook/forecast updates SEPARATI dagli earnings.
- "m_and_a" include rumor di M&A, non solo deal annunciati.
- novelty_score basso (0.1-0.3) per: weekly share repurchase transaction details, routine 8-K
  filings su procedure interne, scheduled dividend.
- novelty_score alto (0.7-1.0) per: surprise CEO change, unexpected M&A, large contract win/loss,
  trial fail, geopolitical escalation.

Output via tool 'classify_event'. NON scrivere altro testo, solo la tool call."""


CLASSIFIER_TOOL = {
    "name": "classify_event",
    "description": "Classifica un evento finanziario e restituisce il risultato strutturato.",
    "input_schema": {
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "enum": EVENT_TYPE_VALUES,
            },
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "company",
                                "person",
                                "country",
                                "commodity",
                                "currency",
                                "etf",
                                "sector",
                                "central_bank",
                                "industry_term",
                            ],
                        },
                        "ticker": {"type": ["string", "null"]},
                        "role": {"type": "string", "enum": ["primary", "mentioned"]},
                    },
                    "required": ["name", "type", "role"],
                },
                "maxItems": 12,
            },
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "novelty_score": {"type": "number", "minimum": 0, "maximum": 1},
            "summary": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "event_type",
            "entities",
            "sentiment",
            "novelty_score",
            "summary",
            "confidence",
        ],
    },
}


class EventClassifier:
    def __init__(self, session: AsyncSession, model: str = HAIKU_MODEL) -> None:
        self.session = session
        self.model = model
        self.api_key = get_settings().anthropic_api_key
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = get_anthropic_client()
        return self._client

    async def classify(self, cluster: EventCluster, raw_events: list[RawEvent]) -> ClassifiedEvent | None:
        """Classifica un singolo cluster via Claude. Ritorna None su fallimento."""
        if not self.api_key:
            logger.warning("classifier_no_api_key", cluster_id=cluster.id)
            return None

        user_text = self._build_user_text(cluster, raw_events)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=cacheable_system(SYSTEM_PROMPT),
                tools=[CLASSIFIER_TOOL],
                tool_choice={"type": "tool", "name": "classify_event"},
                messages=[{"role": "user", "content": user_text}],
            )
        except anthropic.AnthropicError as exc:
            logger.warning("classifier_api_error", cluster_id=cluster.id, error=str(exc))
            return None

        tool_use = next(
            (block for block in response.content if block.type == "tool_use"), None
        )
        if tool_use is None:
            logger.warning("classifier_no_tool_use", cluster_id=cluster.id)
            return None

        try:
            classified = ClassifiedEvent.model_validate(tool_use.input)
        except ValidationError as exc:
            logger.warning(
                "classifier_validation_error",
                cluster_id=cluster.id,
                error=str(exc),
                raw=json.dumps(tool_use.input)[:300],
            )
            return None

        return classified

    async def process_pending(self, limit: int = 100) -> dict[str, int]:
        """Classifica fino a `limit` cluster con event_type='unclassified'."""
        if not self.api_key:
            logger.warning("classifier_skipped_no_key")
            return {"classified": 0, "errored": 0, "skipped": 0}

        clusters = await self._fetch_unclassified(limit)
        if not clusters:
            return {"classified": 0, "errored": 0, "skipped": 0}

        classified_count = 0
        errored = 0
        skipped = 0

        for cluster in clusters:
            raw_events = await self._fetch_raw_events_for(cluster.id)
            try:
                result = await self.classify(cluster, raw_events)
                if result is None:
                    errored += 1
                    continue

                cluster.event_type = result.event_type
                cluster.summary = result.summary
                cluster.novelty_score = result.novelty_score

                # Link entities (creates if missing, attaches to event_entities).
                await link_entities(
                    self.session,
                    cluster_id=cluster.id,
                    entities=result.entities,
                )

                await self.session.commit()
                classified_count += 1
            except Exception as exc:
                await self.session.rollback()
                logger.warning("classifier_iter_error", cluster_id=cluster.id, error=str(exc))
                errored += 1

        logger.info(
            "classifier_run_complete",
            classified=classified_count,
            errored=errored,
            skipped=skipped,
        )
        return {"classified": classified_count, "errored": errored, "skipped": skipped}

    async def _fetch_unclassified(self, limit: int) -> list[EventCluster]:
        result = await self.session.execute(
            select(EventCluster)
            .where(EventCluster.event_type == "unclassified")
            .order_by(EventCluster.first_seen.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _fetch_raw_events_for(self, cluster_id: int, max_events: int = 5) -> list[RawEvent]:
        """Pochi raw_events bastano per dare contesto al classifier (i duplicati semantici
        ripetono le stesse info)."""
        result = await self.session.execute(
            select(RawEvent)
            .where(RawEvent.cluster_id == cluster_id)
            .order_by(RawEvent.published_at.asc())
            .limit(max_events)
        )
        return list(result.scalars().all())

    @staticmethod
    def _build_user_text(cluster: EventCluster, raw_events: Iterable[RawEvent]) -> str:
        lines: list[str] = [f"HEADLINE: {cluster.headline_canonical}"]
        sources_seen: set[str] = set()
        for event in raw_events:
            tag = event.source.split(":")[0]
            if tag in sources_seen:
                continue
            sources_seen.add(tag)
            if event.body:
                body = event.body.strip()[:300]
                lines.append(f"[{event.source}] {event.headline}\n  {body}")
            else:
                lines.append(f"[{event.source}] {event.headline}")
        return "\n\n".join(lines)
