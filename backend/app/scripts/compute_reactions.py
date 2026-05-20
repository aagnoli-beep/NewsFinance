"""CLI: calcola market reactions per cluster con exposures.

Uso:
    uv run python -m app.scripts.compute_reactions --limit 50
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from app.agents.market_reaction import MarketReactionEngine
from app.core.db import SessionLocal


async def main(limit: int) -> int:
    async with SessionLocal() as session:
        engine = MarketReactionEngine(session)
        counts = await engine.process_pending(limit=limit)
    logger.info("reactions_done", **counts)
    print(f"\nCluster processati: {counts['computed']}")
    print(f"Errori:             {counts['errored']}")
    print(f"Rows scritte:       {counts['rows']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
