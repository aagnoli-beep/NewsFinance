"""CLI: lancia un ingester ad-hoc per testing locale.

Uso:
    uv run python -m app.scripts.run_ingester rss
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.core.db import SessionLocal
from app.ingestion.base import NewsIngester
from app.ingestion.rss import RSSIngester
from app.ingestion.sec_edgar import SECEdgarIngester

REGISTRY: dict[str, type[NewsIngester]] = {
    "rss": RSSIngester,
    "sec_edgar": SECEdgarIngester,
}


async def main(name: str) -> int:
    ingester_cls = REGISTRY.get(name)
    if ingester_cls is None:
        available = ", ".join(REGISTRY)
        print(f"Ingester sconosciuto: {name!r}. Disponibili: {available}", file=sys.stderr)
        return 1

    async with SessionLocal() as session:
        ingester = ingester_cls(session)
        new = await ingester.run()
        logger.info("script_done", ingester=name, new=new)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m app.scripts.run_ingester <nome>", file=sys.stderr)
        sys.exit(1)
    sys.exit(asyncio.run(main(sys.argv[1])))
