"""CLI: classifica i cluster con event_type='unclassified'.

Uso:
    uv run python -m app.scripts.classify_clusters --limit 50
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from app.agents.event_classifier import EventClassifier
from app.core.db import SessionLocal


async def main(limit: int) -> int:
    async with SessionLocal() as session:
        classifier = EventClassifier(session)
        counts = await classifier.process_pending(limit=limit)
    logger.info("classify_done", **counts)
    print(f"\nClassificati:  {counts['classified']}")
    print(f"Errori:        {counts['errored']}")
    print(f"Skipped:       {counts['skipped']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
