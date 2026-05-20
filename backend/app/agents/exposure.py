"""Exposure graph engine — per ogni cluster, mappa gli asset esposti all'evento.

Tipi di exposure:
- direct: ticker dell'entità primaria stessa (hop=0, weight=1.0)
- peer: aziende dello stesso settore (hop=1, weight da entity_links)
- supplier/customer: dalla supply chain seedata
- etf: sector ETF che contiene l'entità (hop=1, weight=0.4)
- commodity: per eventi su commodity, ETF di tracking
- sector: indica esposizione settoriale aggregata

Algoritmo:
1. Estrae entità primary dal cluster (con role='primary')
2. Per ogni entità primary con ticker:
   - aggiunge come direct exposure
   - traverso outgoing entity_links → aggiunge come exposure indiretta
3. Per entità mentioned (role='mentioned') → exposure low weight
4. LLM enrichment (Sonnet) per entità non presenti nel graph seedato,
   skippato se ANTHROPIC_API_KEY mancante.

Output: rows in `exposures` con UNIQUE su (cluster_id, asset_ticker).
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import anthropic
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.llm import HAIKU_MODEL, cacheable_system, get_anthropic_client
from app.models.entities import Entity, EntityLink, LinkType
from app.models.events import EventCluster, EventEntity, Exposure, ExposureType

SYSTEM_PROMPT_ENRICH = """Sei un analista che identifica gli asset USA esposti a un evento.

Riceverai una headline di evento e zero o più ticker già noti. Devi proporre
ulteriori asset USA quotati (S&P 500 o ETF noto) che SARANNO potenzialmente
impattati dall'evento, NON dall'azienda menzionata direttamente.

Regole:
- Massimo 5 ticker proposti.
- Solo ticker reali quotati USA (NYSE/Nasdaq) o ETF SPDR/iShares noti.
- Per ogni ticker indica relationship: peer/supplier/customer/etf/commodity.
- weight 0.3-0.7 a seconda della forza del link.
- rationale: 1 frase che spiega il link.

NON ripetere i ticker già noti. Restituisci tool 'enrich_exposure'."""


ENRICH_TOOL = {
    "name": "enrich_exposure",
    "description": "Propone ulteriori asset esposti all'evento basandosi su conoscenza di mercato.",
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "relationship": {
                            "type": "string",
                            "enum": ["peer", "supplier", "customer", "etf", "commodity", "sector"],
                        },
                        "weight": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "rationale": {"type": "string"},
                    },
                    "required": ["ticker", "relationship", "weight", "rationale"],
                },
            },
        },
        "required": ["suggestions"],
    },
}


# Mapping da LinkType a ExposureType
LINK_TO_EXPOSURE: dict[LinkType, ExposureType] = {
    LinkType.PEER: ExposureType.PEER,
    LinkType.SUPPLIER: ExposureType.SUPPLIER,
    LinkType.CUSTOMER: ExposureType.CUSTOMER,
    LinkType.ETF_HOLDING: ExposureType.ETF,
    LinkType.COMMODITY_EXPOSURE: ExposureType.COMMODITY,
    LinkType.COUNTRY_EXPOSURE: ExposureType.COUNTRY,
    LinkType.SUBSIDIARY: ExposureType.DIRECT,
}


class _Suggestion(BaseModel):
    ticker: str
    relationship: str
    weight: float = Field(ge=0, le=1)
    rationale: str


class _EnrichResult(BaseModel):
    suggestions: list[_Suggestion]


class ExposureEngine:
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

    async def process_pending(self, limit: int = 50) -> dict[str, int]:
        """Calcola exposures per i cluster classificati senza exposures."""
        pending = await self._fetch_pending(limit)
        if not pending:
            return {"computed": 0, "errored": 0, "exposures_total": 0}

        computed = 0
        errored = 0
        total_exposures = 0

        for cluster in pending:
            try:
                exposures = await self._compute_for_cluster(cluster)
                if not exposures:
                    # Cluster senza primary entities con ticker → niente exposure
                    # Comunque marca come "processato" inserendo una row dummy?
                    # No, lasciamo vuoto. Sarà ri-tentato al prossimo run se viene aggiunta una entity.
                    continue
                await self._persist_exposures(cluster.id, exposures)
                await self.session.commit()
                computed += 1
                total_exposures += len(exposures)
            except Exception as exc:
                await self.session.rollback()
                logger.warning(
                    "exposure_iter_error", cluster_id=cluster.id, error=str(exc)
                )
                errored += 1

        logger.info(
            "exposure_run_complete",
            computed=computed,
            errored=errored,
            exposures_total=total_exposures,
        )
        return {
            "computed": computed,
            "errored": errored,
            "exposures_total": total_exposures,
        }

    async def _fetch_pending(self, limit: int) -> list[EventCluster]:
        result = await self.session.execute(
            select(EventCluster)
            .outerjoin(Exposure, Exposure.cluster_id == EventCluster.id)
            .where(EventCluster.event_type != "unclassified")
            .where(Exposure.id.is_(None))
            .order_by(EventCluster.first_seen.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _compute_for_cluster(
        self, cluster: EventCluster
    ) -> list[tuple[str, ExposureType, int, float, str]]:
        """Restituisce list di tuple: (ticker, exposure_type, hop, weight, rationale)."""
        # Fetch primary entities + mentioned
        ents_q = (
            select(Entity, EventEntity.role)
            .join(EventEntity, EventEntity.entity_id == Entity.id)
            .where(EventEntity.cluster_id == cluster.id)
        )
        rows = (await self.session.execute(ents_q)).all()
        if not rows:
            return []

        primary_entities = [(e, role) for e, role in rows if role == "primary"]
        mentioned_entities = [(e, role) for e, role in rows if role != "primary"]

        exposures: dict[str, tuple[str, ExposureType, int, float, str]] = {}

        # 1. Direct exposure per primary entities con ticker
        for entity, _ in primary_entities:
            if entity.ticker:
                exposures[entity.ticker] = (
                    entity.ticker,
                    ExposureType.DIRECT,
                    0,
                    1.0,
                    f"primary entity ({entity.name})",
                )

        # 2. Traversal entity_links per ogni primary entity
        for entity, _ in primary_entities:
            await self._add_linked_exposures(entity, exposures, hop=1)

        # 3. Mentioned entities → exposure leggera direct
        for entity, _ in mentioned_entities:
            if entity.ticker and entity.ticker not in exposures:
                exposures[entity.ticker] = (
                    entity.ticker,
                    ExposureType.DIRECT,
                    0,
                    0.5,
                    f"mentioned entity ({entity.name})",
                )

        # 4. Sector/commodity exposure inferito dalle entità non-ticker (countries, commodities)
        for entity, _ in primary_entities + mentioned_entities:
            if entity.ticker:
                continue
            if entity.type == "commodity":
                # Mapping volutamente semplice: nome del commodity → ETF proxy
                proxy = self._commodity_to_etf(entity.name)
                if proxy and proxy not in exposures:
                    exposures[proxy] = (
                        proxy,
                        ExposureType.COMMODITY,
                        1,
                        0.7,
                        f"commodity exposure ({entity.name})",
                    )

        # 5. LLM enrichment (opzionale)
        if self.api_key and len(exposures) < 8:
            try:
                enriched = await self._llm_enrich(cluster, list(exposures.keys()))
                for sug in enriched:
                    if sug.ticker in exposures:
                        continue
                    exposures[sug.ticker] = (
                        sug.ticker,
                        self._relationship_to_exposure(sug.relationship),
                        1,
                        sug.weight,
                        f"llm_suggested: {sug.rationale[:200]}",
                    )
            except Exception as exc:
                logger.debug("llm_enrich_failed", cluster_id=cluster.id, error=str(exc))

        return list(exposures.values())

    async def _add_linked_exposures(
        self,
        entity: Entity,
        exposures: dict[str, tuple[str, ExposureType, int, float, str]],
        hop: int,
    ) -> None:
        """Aggiunge a `exposures` i target dei link uscenti dell'entità."""
        links_q = (
            select(EntityLink, Entity)
            .join(Entity, Entity.id == EntityLink.to_entity_id)
            .where(EntityLink.from_entity_id == entity.id)
        )
        for link, target in (await self.session.execute(links_q)).all():
            if not target.ticker or target.ticker in exposures:
                continue
            exposure_type = LINK_TO_EXPOSURE.get(link.link_type, ExposureType.PEER)
            exposures[target.ticker] = (
                target.ticker,
                exposure_type,
                hop,
                link.weight,
                f"{link.link_type} of {entity.name} ({entity.ticker or '—'})",
            )

    @staticmethod
    def _relationship_to_exposure(rel: str) -> ExposureType:
        mapping = {
            "peer": ExposureType.PEER,
            "supplier": ExposureType.SUPPLIER,
            "customer": ExposureType.CUSTOMER,
            "etf": ExposureType.ETF,
            "commodity": ExposureType.COMMODITY,
            "sector": ExposureType.SECTOR,
        }
        return mapping.get(rel, ExposureType.PEER)

    @staticmethod
    def _commodity_to_etf(commodity_name: str) -> str | None:
        n = commodity_name.lower()
        if "gold" in n:
            return "GLD"
        if "silver" in n:
            return "SLV"
        if "wti" in n or "crude" in n or "petrol" in n:
            return "USO"
        if "brent" in n:
            return "BNO"
        if "gas" in n and "natural" in n:
            return "UNG"
        return None

    async def _llm_enrich(
        self, cluster: EventCluster, known_tickers: list[str]
    ) -> list[_Suggestion]:
        if not self.api_key:
            return []
        user_text = (
            f"HEADLINE: {cluster.headline_canonical}\n"
            + (f"SUMMARY: {cluster.summary}\n" if cluster.summary else "")
            + f"EVENT TYPE: {cluster.event_type}\n"
            + f"TICKER GIÀ NOTI: {', '.join(known_tickers) if known_tickers else '—'}"
        )
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=cacheable_system(SYSTEM_PROMPT_ENRICH),
                tools=[ENRICH_TOOL],
                tool_choice={"type": "tool", "name": "enrich_exposure"},
                messages=[{"role": "user", "content": user_text}],
            )
        except anthropic.AnthropicError as exc:
            logger.debug("exposure_llm_error", cluster_id=cluster.id, error=str(exc))
            return []

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            return []
        try:
            result = _EnrichResult.model_validate(tool_use.input)
        except ValidationError as exc:
            logger.debug(
                "exposure_validation_error",
                cluster_id=cluster.id,
                error=str(exc),
                raw=json.dumps(tool_use.input)[:200],
            )
            return []
        return result.suggestions

    async def _persist_exposures(
        self,
        cluster_id: int,
        exposures: Iterable[tuple[str, ExposureType, int, float, str]],
    ) -> None:
        for ticker, exposure_type, hop, weight, rationale in exposures:
            stmt = (
                insert(Exposure)
                .values(
                    cluster_id=cluster_id,
                    asset_ticker=ticker,
                    exposure_type=exposure_type,
                    hop_distance=hop,
                    weight=weight,
                    rationale=rationale,
                )
                .on_conflict_do_update(
                    constraint="uq_exposure_cluster_ticker",
                    set_={
                        "exposure_type": exposure_type,
                        "hop_distance": hop,
                        "weight": weight,
                        "rationale": rationale,
                    },
                )
            )
            await self.session.execute(stmt)
