"""API endpoints per Coverage: stato del backfill prezzi."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.data.universe import UNIVERSE
from app.models.market import Price

router = APIRouter(prefix="/coverage", tags=["coverage"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class TickerCoverage(BaseModel):
    ticker: str
    bars: int
    first_ts: date | None
    last_ts: date | None
    last_close: float | None


class CoverageResponse(BaseModel):
    universe_size: int
    covered_tickers: int
    missing_tickers: list[str]
    total_bars: int
    by_ticker: list[TickerCoverage]


@router.get("", response_model=CoverageResponse)
async def get_coverage(session: SessionDep) -> CoverageResponse:
    """Per ogni ticker dell'universe, mostra range + ultimo prezzo."""
    rows = (
        await session.execute(
            select(
                Price.ticker,
                func.count().label("bars"),
                func.min(Price.ts).label("first_ts"),
                func.max(Price.ts).label("last_ts"),
            )
            .group_by(Price.ticker)
            .order_by(desc("bars"))
        )
    ).all()

    coverage_map: dict[str, dict] = {
        ticker: {
            "ticker": ticker,
            "bars": bars,
            "first_ts": first_ts.date() if first_ts else None,
            "last_ts": last_ts.date() if last_ts else None,
            "last_close": None,
        }
        for ticker, bars, first_ts, last_ts in rows
    }

    # Riempi last_close con una query separata su (ticker, max(ts)).
    for ticker, info in coverage_map.items():
        last = await session.execute(
            select(Price.close).where(Price.ticker == ticker).order_by(desc(Price.ts)).limit(1)
        )
        info["last_close"] = last.scalar()

    covered = set(coverage_map.keys())
    missing = [t for t in UNIVERSE if t not in covered]

    by_ticker = [TickerCoverage(**info) for info in coverage_map.values()]
    total_bars = sum(info["bars"] for info in coverage_map.values())

    return CoverageResponse(
        universe_size=len(UNIVERSE),
        covered_tickers=len(covered),
        missing_tickers=missing,
        total_bars=total_bars,
        by_ticker=by_ticker,
    )
