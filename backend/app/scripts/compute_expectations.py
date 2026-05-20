"""CLI: calcola expectation per i cluster classificati senza expectation.

Uso:
    uv run python -m app.scripts.compute_expectations --limit 30
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from app.agents.expectation import ExpectationEngine
from app.core.db import SessionLocal


async def main(limit: int) -> int:
    async with SessionLocal() as session:
        engine = ExpectationEngine(session)
        counts = await engine.process_pending(limit=limit)
    logger.info("expectations_done", **counts)
    print(f"\nComputate:   {counts['computed']}")
    print(f"Skippate:    {counts['skipped']}")
    print(f"Errori:      {counts['errored']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
