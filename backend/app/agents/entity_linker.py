"""Entity linker: collega entità estratte dal classifier alle righe `entities` canoniche.

Strategia (in ordine):
1. Match per ticker (case-insensitive) se presente → entità canonica esiste
2. Match per name esatto case-insensitive
3. Crea nuova entity (llm_suggested=true implicito tramite metadata)

Skip industry_term: troppo vago per essere un'entità tracciabile.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import ClassifiedEntity
from app.models.entities import Entity
from app.models.events import EventEntity


async def link_entities(
    session: AsyncSession,
    cluster_id: int,
    entities: list[ClassifiedEntity],
) -> int:
    """Risolve ogni ClassifiedEntity a un Entity.id e crea EventEntity.

    Ritorna il numero di entità linkate (escluse industry_term).
    """
    linked = 0
    for ent in entities:
        if ent.type == "industry_term":
            continue

        entity_id = await _find_or_create_entity(session, ent)
        if entity_id is None:
            continue

        # Upsert su event_entities (PK composta cluster_id+entity_id).
        stmt = (
            insert(EventEntity)
            .values(cluster_id=cluster_id, entity_id=entity_id, role=ent.role)
            .on_conflict_do_update(
                index_elements=["cluster_id", "entity_id"],
                set_={"role": ent.role},
            )
        )
        await session.execute(stmt)
        linked += 1

    return linked


async def _find_or_create_entity(
    session: AsyncSession, ent: ClassifiedEntity
) -> int | None:
    """Match per ticker, poi per name. Crea se nessun match."""
    # 1. Match per ticker se presente
    if ent.ticker:
        ticker_upper = ent.ticker.upper().strip()
        result = await session.execute(
            select(Entity.id).where(Entity.ticker == ticker_upper)
        )
        existing = result.scalar()
        if existing:
            return existing

    # 2. Match per nome case-insensitive
    name_norm = ent.name.strip()
    if not name_norm:
        return None
    result = await session.execute(
        select(Entity.id).where(func.lower(Entity.name) == name_norm.lower())
    )
    existing = result.scalar()
    if existing:
        # Se il classifier ha trovato un ticker nuovo per un'entità esistente senza ticker,
        # potremmo arricchirla. Per semplicità in MVP non lo facciamo.
        return existing

    # 3. Crea nuova entity
    try:
        entity = Entity(
            type=ent.type,
            name=name_norm,
            ticker=ent.ticker.upper().strip() if ent.ticker else None,
            meta={"discovered_by": "event_classifier"},
        )
        session.add(entity)
        await session.flush()
        return entity.id
    except Exception as exc:
        # Probabilmente conflict su ticker unique constraint (race condition).
        # Riprova lookup.
        await session.rollback()
        logger.debug("entity_create_conflict_retry", name=name_norm, error=str(exc))
        if ent.ticker:
            ticker_upper = ent.ticker.upper().strip()
            result = await session.execute(
                select(Entity.id).where(Entity.ticker == ticker_upper)
            )
            existing = result.scalar()
            if existing:
                return existing
        return None
