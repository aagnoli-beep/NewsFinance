"""CLI: clusterizza i raw_events pendenti.

Uso:
    uv run python -m app.scripts.run_dedup
    uv run python -m app.scripts.run_dedup --limit 1000
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from app.core.db import SessionLocal
from app.ingestion.dedup import DedupEngine


async def main(limit: int) -> int:
    async with SessionLocal() as session:
        engine = DedupEngine(session)
        counts = await engine.process_pending(limit=limit)
    logger.info("dedup_done", **counts)
    print(f"\nNuovi cluster:       {counts['clustered_new']}")
    print(f"Attaccati a esistenti: {counts['clustered_existing']}")
    print(f"Errori:              {counts['errored']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
