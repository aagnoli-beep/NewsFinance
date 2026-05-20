"""CLI: calcola exposures per cluster classificati senza exposures.

Uso:
    uv run python -m app.scripts.compute_exposures --limit 50
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from app.agents.exposure import ExposureEngine
from app.core.db import SessionLocal


async def main(limit: int) -> int:
    async with SessionLocal() as session:
        engine = ExposureEngine(session)
        counts = await engine.process_pending(limit=limit)
    logger.info("exposures_done", **counts)
    print(f"\nCluster con exposures: {counts['computed']}")
    print(f"Errori:                 {counts['errored']}")
    print(f"Exposures totali:       {counts['exposures_total']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
