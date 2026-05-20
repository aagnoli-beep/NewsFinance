"""Expectation engine: per ogni cluster classificato, calcola surprise vs baseline.

Strategie per tipo evento:
- earnings → pull EPS/revenue consensus da Finnhub (raw_meta dell'evento earnings_upcoming
  o da `/stock/earnings`). Compara actual vs estimate.
- macro_data → usa la observation precedente come baseline; magnitudine = |delta/std|.
  Free tier non ha consensus survey, quindi è una proxy "delta vs prior".
- central_bank, m_and_a, contract, geopolitical, etc. → LLM inference da news prior
  sulla stessa entità negli ultimi 90 giorni (Sonnet 4.6 con caching).

Output: una riga in `expectations` per cluster (PK = cluster_id, quindi unique).
"""

from __future__ import annotations

import json
from datetime import timedelta

import anthropic
from loguru import logger
from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import ExpectationResult
from app.core.config import get_settings
from app.core.llm import SONNET_MODEL, cacheable_system, get_anthropic_client
from app.models.events import EventCluster, Expectation, RawEvent

SYSTEM_PROMPT_QUALITATIVE = """Sei un analista finanziario che valuta la sorpresa di un evento di mercato.

Riceverai:
- evento corrente classificato
- 0-N news precedenti sulla stessa entità negli ultimi 90 giorni

Compito: stabilire se l'evento è una sorpresa positiva, negativa, neutra o incerta
rispetto a quello che il mercato si aspettava SULLA BASE delle news precedenti.

Logica:
- Se non c'è contesto precedente sufficiente, baseline_source = "no_baseline" e
  surprise_direction può essere "uncertain". Magnitudine = "low".
- Se il contesto suggerisce attese alte (es. "Boeing rumored to win 500-jet order")
  e l'evento è inferiore (es. "Boeing wins 200-jet order"), → surprise NEGATIVA.
- Se il contesto è neutro e l'evento è materiale (es. "unexpected CEO resignation"),
  → direction in linea con l'evento, magnitude medium/high.
- expected_value e actual_value: 1 frase ciascuno o valore numerico.
- surprise_zscore: lascialo null per eventi qualitativi.
- rationale: spiega in 2-3 frasi perché.

Output via tool 'compute_expectation'."""


QUALITATIVE_TOOL = {
    "name": "compute_expectation",
    "description": "Computa il surprise di un evento basandosi sul contesto precedente.",
    "input_schema": {
        "type": "object",
        "properties": {
            "baseline_source": {
                "type": "string",
                "enum": [
                    "llm_inference_from_prior_news",
                    "no_baseline",
                ],
            },
            "expected_value": {"type": ["string", "null"]},
            "actual_value": {"type": ["string", "null"]},
            "surprise_direction": {
                "type": "string",
                "enum": ["positive", "negative", "neutral", "uncertain"],
            },
            "surprise_magnitude": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "baseline_source",
            "surprise_direction",
            "surprise_magnitude",
            "rationale",
        ],
    },
}


# Event type che hanno un loro path strutturato (no LLM).
STRUCTURED_TYPES = {"earnings", "macro_data"}

# Event type che skippiamo dall'expectation engine (sono "watch only" o troppo rumorosi).
SKIP_TYPES = {"other", "analyst_rating", "unclassified"}


class ExpectationEngine:
    def __init__(self, session: AsyncSession, model: str = SONNET_MODEL) -> None:
        self.session = session
        self.model = model
        self.api_key = get_settings().anthropic_api_key
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = get_anthropic_client()
        return self._client

    async def process_pending(self, limit: int = 50) -> dict[str, int]:
        """Itera sui cluster classificati senza expectation e calcola la sorpresa."""
        pending = await self._fetch_pending(limit)
        if not pending:
            return {"computed": 0, "skipped": 0, "errored": 0}

        computed = 0
        skipped = 0
        errored = 0

        for cluster in pending:
            try:
                if cluster.event_type in SKIP_TYPES:
                    skipped += 1
                    continue

                result = await self._compute_for_cluster(cluster)
                if result is None:
                    errored += 1
                    continue

                await self._persist_expectation(cluster.id, result)
                await self.session.commit()
                computed += 1
            except Exception as exc:
                await self.session.rollback()
                logger.warning(
                    "expectation_iter_error", cluster_id=cluster.id, error=str(exc)
                )
                errored += 1

        logger.info(
            "expectation_run_complete",
            computed=computed,
            skipped=skipped,
            errored=errored,
        )
        return {"computed": computed, "skipped": skipped, "errored": errored}

    async def _fetch_pending(self, limit: int) -> list[EventCluster]:
        # cluster classificati ma senza una expectation associata
        result = await self.session.execute(
            select(EventCluster)
            .outerjoin(Expectation, Expectation.cluster_id == EventCluster.id)
            .where(EventCluster.event_type != "unclassified")
            .where(Expectation.id.is_(None))
            .order_by(EventCluster.first_seen.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _compute_for_cluster(self, cluster: EventCluster) -> ExpectationResult | None:
        if cluster.event_type == "earnings":
            return await self._compute_earnings(cluster)
        if cluster.event_type == "macro_data":
            return await self._compute_macro(cluster)
        # Tutto il resto → LLM inference (richiede API key)
        if not self.api_key:
            return None
        return await self._compute_qualitative(cluster)

    async def _compute_earnings(self, cluster: EventCluster) -> ExpectationResult | None:
        """Cerca l'EPS estimate da raw_meta di un raw_event finnhub:earnings_calendar
        sulla stessa entità + giorno. Se non trovato, fallback su qualitative LLM."""
        raw = await self._fetch_first_raw(cluster.id)
        if raw is None:
            return None

        # Se il cluster è già un finnhub earnings_calendar, l'EPS estimate è nel raw_meta.
        meta = raw.raw_meta or {}
        if raw.source == "finnhub:earnings_calendar":
            symbol = meta.get("symbol")
            eps_est = meta.get("eps_estimate")
            eps_actual = meta.get("eps_actual")
            rev_est = meta.get("revenue_estimate")
            rev_actual = meta.get("revenue_actual")

            if eps_actual is None and rev_actual is None:
                # Solo upcoming, attesa non ancora confrontabile
                return ExpectationResult(
                    baseline_source="finnhub_consensus",
                    expected_value=f"EPS estimate: {eps_est}, Revenue estimate: {rev_est}",
                    actual_value=None,
                    surprise_direction="neutral",
                    surprise_magnitude="low",
                    surprise_zscore=None,
                    rationale=(
                        f"Earnings {symbol} programmato. EPS estimate {eps_est}. "
                        "Attesa di confronto post-pubblicazione."
                    ),
                )

            direction, magnitude, z = self._earnings_surprise(eps_est, eps_actual)
            return ExpectationResult(
                baseline_source="finnhub_consensus",
                expected_value=f"EPS estimate: {eps_est}, Revenue estimate: {rev_est}",
                actual_value=f"EPS actual: {eps_actual}, Revenue actual: {rev_actual}",
                surprise_direction=direction,
                surprise_magnitude=magnitude,
                surprise_zscore=z,
                rationale=(
                    f"{symbol}: EPS {eps_actual} vs {eps_est} consensus → "
                    f"{direction} surprise ({magnitude})"
                ),
            )

        # Se earnings da news (es. Polygon/Finnhub news) → qualitative
        if not self.api_key:
            return None
        return await self._compute_qualitative(cluster)

    @staticmethod
    def _earnings_surprise(
        estimate: float | None, actual: float | None
    ) -> tuple[str, str, float | None]:
        if estimate is None or actual is None or estimate == 0:
            return "uncertain", "low", None
        delta = actual - estimate
        pct = abs(delta / estimate) if estimate != 0 else 0
        direction = "positive" if delta > 0 else ("negative" if delta < 0 else "neutral")
        if pct < 0.03:
            magnitude = "low"
        elif pct < 0.10:
            magnitude = "medium"
        else:
            magnitude = "high"
        # z-score approssimato usando 5% std (proxy ragionevole per EPS std consensus)
        zscore = delta / (abs(estimate) * 0.05) if estimate != 0 else None
        return direction, magnitude, zscore

    async def _compute_macro(self, cluster: EventCluster) -> ExpectationResult | None:
        """Per macro release: usa il valore della release precedente come baseline."""
        raw = await self._fetch_first_raw(cluster.id)
        if raw is None:
            return None

        meta = raw.raw_meta or {}
        if not raw.source.startswith("fred:"):
            # Macro news non strutturata → LLM
            if not self.api_key:
                return None
            return await self._compute_qualitative(cluster)

        series_id = meta.get("series_id")
        label = meta.get("label")
        current_value = meta.get("value")
        obs_date = meta.get("observation_date")

        prior = await self._fetch_prior_macro(series_id, current_obs_date=obs_date)
        if prior is None:
            return ExpectationResult(
                baseline_source="no_baseline",
                expected_value=None,
                actual_value=f"{label}: {current_value}",
                surprise_direction="neutral",
                surprise_magnitude="low",
                surprise_zscore=None,
                rationale="Nessun valore precedente trovato in raw_events; baseline assente.",
            )

        prior_value = prior.raw_meta.get("value") if prior.raw_meta else None
        if prior_value is None or prior_value == 0:
            return ExpectationResult(
                baseline_source="fred_prior_release",
                expected_value=f"{label}: {prior_value} (prior)",
                actual_value=f"{label}: {current_value}",
                surprise_direction="uncertain",
                surprise_magnitude="low",
                surprise_zscore=None,
                rationale="Baseline esistente ma confronto non calcolabile.",
            )

        delta = float(current_value) - float(prior_value)
        pct = abs(delta / float(prior_value)) if float(prior_value) != 0 else 0
        direction = "positive" if delta > 0 else ("negative" if delta < 0 else "neutral")
        if pct < 0.01:
            magnitude = "low"
        elif pct < 0.05:
            magnitude = "medium"
        else:
            magnitude = "high"

        return ExpectationResult(
            baseline_source="fred_prior_release",
            expected_value=f"{label}: {prior_value} (prior)",
            actual_value=f"{label}: {current_value}",
            surprise_direction=direction,
            surprise_magnitude=magnitude,
            surprise_zscore=None,
            rationale=(
                f"{label}: {current_value} vs prior {prior_value} ({pct:.2%} change) "
                f"→ {direction} {magnitude}."
            ),
        )

    async def _fetch_prior_macro(
        self, series_id: str, current_obs_date: str | None
    ) -> RawEvent | None:
        if not series_id or not current_obs_date:
            return None
        result = await self.session.execute(
            select(RawEvent)
            .where(RawEvent.source == f"fred:{series_id.lower()}")
            .where(RawEvent.raw_meta["observation_date"].as_string() != current_obs_date)
            .order_by(desc(RawEvent.published_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _fetch_first_raw(self, cluster_id: int) -> RawEvent | None:
        result = await self.session.execute(
            select(RawEvent)
            .where(RawEvent.cluster_id == cluster_id)
            .order_by(RawEvent.published_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _compute_qualitative(self, cluster: EventCluster) -> ExpectationResult | None:
        """LLM-based: prende le news più recenti sulla stessa entità + l'evento corrente,
        chiede a Sonnet di valutare la sorpresa."""
        if not self.api_key:
            return None

        prior_news = await self._fetch_prior_news_for_cluster(cluster)
        user_text = self._build_qualitative_text(cluster, prior_news)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=cacheable_system(SYSTEM_PROMPT_QUALITATIVE),
                tools=[QUALITATIVE_TOOL],
                tool_choice={"type": "tool", "name": "compute_expectation"},
                messages=[{"role": "user", "content": user_text}],
            )
        except anthropic.AnthropicError as exc:
            logger.warning("expectation_api_error", cluster_id=cluster.id, error=str(exc))
            return None

        tool_use = next(
            (block for block in response.content if block.type == "tool_use"), None
        )
        if tool_use is None:
            return None

        try:
            return ExpectationResult.model_validate(tool_use.input)
        except ValidationError as exc:
            logger.warning(
                "expectation_validation_error",
                cluster_id=cluster.id,
                error=str(exc),
                raw=json.dumps(tool_use.input)[:300],
            )
            return None

    async def _fetch_prior_news_for_cluster(
        self, cluster: EventCluster, lookback_days: int = 90, limit: int = 10
    ) -> list[RawEvent]:
        """News dei 90 giorni prima del cluster sulle stesse entità primarie."""
        from app.models.events import EventEntity

        # Ricava primary entities del cluster
        primary_entities_q = (
            select(EventEntity.entity_id)
            .where(EventEntity.cluster_id == cluster.id)
            .where(EventEntity.role == "primary")
        )
        primary_ids = list((await self.session.execute(primary_entities_q)).scalars().all())
        if not primary_ids:
            return []

        cutoff = cluster.first_seen - timedelta(days=lookback_days)

        # Trova altri cluster recenti su quelle entità primarie
        prior_clusters_q = (
            select(EventEntity.cluster_id)
            .where(EventEntity.entity_id.in_(primary_ids))
            .where(EventEntity.cluster_id != cluster.id)
            .distinct()
        )
        prior_cluster_ids = list(
            (await self.session.execute(prior_clusters_q)).scalars().all()
        )
        if not prior_cluster_ids:
            return []

        # Pull headline + body dei raw_events di quei cluster
        result = await self.session.execute(
            select(RawEvent)
            .where(RawEvent.cluster_id.in_(prior_cluster_ids))
            .where(RawEvent.published_at >= cutoff)
            .where(RawEvent.published_at < cluster.first_seen)
            .order_by(desc(RawEvent.published_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    def _build_qualitative_text(cluster: EventCluster, prior_news: list[RawEvent]) -> str:
        lines: list[str] = [
            f"EVENTO CORRENTE [{cluster.event_type}]:",
            f"  Headline: {cluster.headline_canonical}",
        ]
        if cluster.summary:
            lines.append(f"  Summary: {cluster.summary}")

        if prior_news:
            lines.append("\nCONTESTO (news ultimi 90 giorni sulle stesse entità):")
            for n in prior_news:
                date_str = n.published_at.date().isoformat() if n.published_at else "?"
                lines.append(f"  [{date_str}] {n.headline}")
        else:
            lines.append("\nCONTESTO: nessuna news prior trovata.")
        return "\n".join(lines)

    async def _persist_expectation(self, cluster_id: int, result: ExpectationResult) -> None:
        stmt = (
            insert(Expectation)
            .values(
                cluster_id=cluster_id,
                baseline_source=result.baseline_source,
                expected_value=result.expected_value,
                actual_value=result.actual_value,
                surprise_direction=result.surprise_direction,
                surprise_magnitude=result.surprise_magnitude,
                surprise_zscore=result.surprise_zscore,
                rationale=result.rationale,
            )
            .on_conflict_do_update(
                index_elements=["cluster_id"],
                set_={
                    "baseline_source": result.baseline_source,
                    "expected_value": result.expected_value,
                    "actual_value": result.actual_value,
                    "surprise_direction": result.surprise_direction,
                    "surprise_magnitude": result.surprise_magnitude,
                    "surprise_zscore": result.surprise_zscore,
                    "rationale": result.rationale,
                },
            )
        )
        await self.session.execute(stmt)
