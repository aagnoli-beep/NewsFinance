"""Astrazioni condivise per gli ingester di news."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import RawEvent


@dataclass(slots=True)
class IngestedItem:
    """News normalizzata, prodotta da ogni ingester prima di entrare in raw_events."""

    source: str
    source_quality: str
    headline: str
    body: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None
    raw_meta: dict = field(default_factory=dict)

    @property
    def url_hash(self) -> str | None:
        """Hash deterministico dell'URL per dedup esatto tra batch."""
        if not self.source_url:
            return None
        normalized = self.source_url.strip().lower().rstrip("/").split("?", 1)[0]
        return hashlib.sha256(normalized.encode()).hexdigest()


class NewsIngester(ABC):
    """Interfaccia comune di un connector di news.

    Sottoclassi implementano `fetch()` che yielda IngestedItem; la base si occupa
    di dedup esatto (per url_hash) e persistenza in raw_events.
    """

    source_name: str = ""
    source_quality: str = "secondary"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @abstractmethod
    def fetch(self) -> AsyncIterator[IngestedItem]:
        """Restituisce un iteratore async di item grezzi dalla fonte."""
        ...

    async def run(self) -> int:
        """Esegue un ciclo di ingestion. Ritorna il numero di item nuovi persistiti."""
        new_count = 0
        seen_count = 0
        errors = 0

        async for item in self.fetch():
            try:
                if await self._exists(item.url_hash):
                    seen_count += 1
                    continue

                self.session.add(
                    RawEvent(
                        source=item.source,
                        source_url=item.source_url,
                        source_quality=item.source_quality,
                        url_hash=item.url_hash,
                        headline=item.headline,
                        body=item.body,
                        published_at=item.published_at,
                        raw_meta=item.raw_meta,
                    )
                )
                new_count += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    "ingester_item_error",
                    source=self.source_name,
                    error=str(exc),
                    url=item.source_url,
                )

        await self.session.commit()
        logger.info(
            "ingester_run_complete",
            source=self.source_name,
            new=new_count,
            duplicate=seen_count,
            errors=errors,
        )
        return new_count

    async def _exists(self, url_hash: str | None) -> bool:
        if not url_hash:
            return False
        result = await self.session.execute(
            select(RawEvent.id).where(RawEvent.url_hash == url_hash).limit(1)
        )
        return result.scalar() is not None
