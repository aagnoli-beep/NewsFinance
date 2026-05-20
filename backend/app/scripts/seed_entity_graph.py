"""CLI: popola tabelle `entities` ed `entity_links` con dati seed.

Esegue:
1. Inserisce/aggiorna Entity per ogni ticker in UNIVERSE (tipo company per
   S&P 500, etf per gli ETF noti).
2. Crea pair sector ETF ↔ tutti i ticker dello stesso settore (link_type=etf_holding).
3. Crea peer link mutui fra ticker dello stesso settore.
4. Crea supply chain link da SUPPLY_CHAIN_LINKS.

Idempotente: usa ON CONFLICT DO NOTHING (entity_links UNIQUE su tripla
from_id/to_id/link_type). Rieseguibile senza duplicati.

Uso:
    uv run python -m app.scripts.seed_entity_graph
"""

from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.data.sectors import (
    BOND_ETFS,
    COMMODITY_ETFS,
    FX_ETFS,
    INDEX_ETFS,
    TICKER_SECTOR,
    VOL_ETFS,
    get_peers,
    get_sector,
)
from app.data.supply_chain import SUPPLY_CHAIN_LINKS
from app.data.universe import UNIVERSE
from app.models.entities import Entity, EntityLink, EntityType, LinkType


async def upsert_entity(
    session: AsyncSession,
    ticker: str,
    name: str,
    entity_type: EntityType,
    sector: str | None = None,
) -> int:
    """Inserisce o restituisce id di Entity esistente per ticker."""
    ticker = ticker.upper()
    existing = (
        await session.execute(select(Entity).where(Entity.ticker == ticker))
    ).scalar_one_or_none()
    if existing:
        # Aggiorna sector se mancante
        if sector and not existing.sector:
            existing.sector = sector
            await session.flush()
        return existing.id

    entity = Entity(
        ticker=ticker,
        name=name,
        type=entity_type,
        sector=sector,
        meta={"seeded": True},
    )
    session.add(entity)
    await session.flush()
    return entity.id


async def upsert_link(
    session: AsyncSession,
    from_id: int,
    to_id: int,
    link_type: LinkType,
    weight: float = 1.0,
) -> None:
    """Insert ON CONFLICT DO NOTHING su (from, to, link_type)."""
    stmt = (
        insert(EntityLink)
        .values(
            from_entity_id=from_id,
            to_entity_id=to_id,
            link_type=link_type,
            weight=weight,
            llm_suggested=False,
            source="seed",
        )
        .on_conflict_do_nothing(
            index_elements=["from_entity_id", "to_entity_id", "link_type"]
        )
    )
    await session.execute(stmt)


async def main() -> int:
    async with SessionLocal() as session:
        entities_created = 0
        links_created = 0

        # 1. Entities per ogni ticker dell'universe
        etf_lookups = {**INDEX_ETFS, **COMMODITY_ETFS, **BOND_ETFS, **FX_ETFS, **VOL_ETFS}

        for ticker in UNIVERSE:
            ticker = ticker.upper()
            sector_info = get_sector(ticker)
            if ticker in etf_lookups:
                entity_type = EntityType.ETF
                name = etf_lookups[ticker]
                sector = None
            elif sector_info:
                entity_type = EntityType.COMPANY
                name = ticker  # nome migliore lo aggiorneremo via classifier
                sector = sector_info[0]
            else:
                # ticker dell'universe senza sector noto (es. ETF settoriale come XLK)
                entity_type = EntityType.ETF
                name = ticker
                sector = None
            await upsert_entity(session, ticker, name, entity_type, sector)
            entities_created += 1

        # Assicura le sector ETF anche se non sono nell'universe
        sector_etfs = {sec[1] for sec in TICKER_SECTOR.values()}
        for etf_ticker in sector_etfs:
            if etf_ticker not in UNIVERSE:
                await upsert_entity(session, etf_ticker, etf_ticker, EntityType.ETF, None)
                entities_created += 1

        await session.commit()
        logger.info("entities_seeded", count=entities_created)

        # 2. Link company → sector ETF (etf_holding)
        for ticker, (_sector_name, etf_ticker) in TICKER_SECTOR.items():
            from_e = (
                await session.execute(select(Entity.id).where(Entity.ticker == ticker))
            ).scalar()
            etf_e = (
                await session.execute(select(Entity.id).where(Entity.ticker == etf_ticker))
            ).scalar()
            if from_e is None or etf_e is None:
                continue
            await upsert_link(session, from_e, etf_e, LinkType.ETF_HOLDING, weight=0.4)
            await upsert_link(session, etf_e, from_e, LinkType.ETF_HOLDING, weight=0.4)
            links_created += 2

        # 3. Peer link mutui fra ticker dello stesso settore
        for ticker in TICKER_SECTOR:
            peers = get_peers(ticker)
            from_e = (
                await session.execute(select(Entity.id).where(Entity.ticker == ticker))
            ).scalar()
            if from_e is None:
                continue
            for peer in peers:
                peer_e = (
                    await session.execute(select(Entity.id).where(Entity.ticker == peer))
                ).scalar()
                if peer_e is None:
                    continue
                await upsert_link(session, from_e, peer_e, LinkType.PEER, weight=0.6)
                links_created += 1

        # 4. Supply chain link curati
        for from_t, to_t, link_type in SUPPLY_CHAIN_LINKS:
            from_e = (
                await session.execute(select(Entity.id).where(Entity.ticker == from_t.upper()))
            ).scalar()
            to_e = (
                await session.execute(select(Entity.id).where(Entity.ticker == to_t.upper()))
            ).scalar()
            if from_e is None or to_e is None:
                continue
            # Sostituiamo "peer" del seed con LinkType.PEER se non già fatto sopra
            lt = LinkType(link_type)
            weight = 0.5 if lt in (LinkType.SUPPLIER, LinkType.CUSTOMER) else 0.6
            await upsert_link(session, from_e, to_e, lt, weight=weight)
            links_created += 1

        await session.commit()
        logger.info("links_seeded", count=links_created)

        # Riepilogo
        total_entities = (
            await session.execute(select(Entity.id).limit(10000))
        ).fetchall()
        total_links = (
            await session.execute(select(EntityLink.id).limit(10000))
        ).fetchall()
        print(f"\nEntities in DB: {len(total_entities)}")
        print(f"Entity links in DB: {len(total_links)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
