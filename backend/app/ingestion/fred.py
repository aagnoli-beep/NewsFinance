"""Ingester FRED — macroeconomic indicators USA.

FRED (Federal Reserve Economic Data, St. Louis Fed) espone tutte le serie
macro USA via REST. Free, illimitato per uso ragionevole.

Tracciamo le serie più rilevanti per market impact:
- CPIAUCSL: CPI All Urban Consumers
- PAYEMS: Non-Farm Payrolls
- UNRATE: Unemployment Rate
- FEDFUNDS: Federal Funds Rate effective
- DGS10: 10-Year Treasury constant maturity
- DEXUSEU: USD/EUR exchange rate
- DCOILWTICO: WTI spot
- DCOILBRENTEU: Brent spot
- DJIA, SP500, NASDAQCOM: indici di riferimento

Ogni nuova observation diventa un raw_event con qualità "primary" (Fed) e
viene poi clusterizzato come "macro_release". Da Fase 3 l'expectation engine
calcola surprise vs consensus.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
from loguru import logger

from app.core.config import get_settings
from app.ingestion.base import IngestedItem, NewsIngester

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"

# Serie FRED da monitorare + label leggibili (mostrate nell'headline).
FRED_SERIES: list[tuple[str, str]] = [
    ("CPIAUCSL", "CPI All Urban Consumers"),
    ("CPILFESL", "Core CPI (ex Food & Energy)"),
    ("PAYEMS", "Non-Farm Payrolls"),
    ("UNRATE", "Unemployment Rate"),
    ("FEDFUNDS", "Fed Funds Rate (effective)"),
    ("DFEDTARU", "Fed Funds Target Upper"),
    ("DGS10", "10-Year Treasury Yield"),
    ("DGS2", "2-Year Treasury Yield"),
    ("DEXUSEU", "USD/EUR Exchange Rate"),
    ("DCOILWTICO", "WTI Crude Oil"),
    ("DCOILBRENTEU", "Brent Crude Oil"),
    ("GOLDAMGBD228NLBM", "Gold Fixing Price (LBMA)"),
    ("VIXCLS", "VIX Close"),
    ("T10Y2Y", "10Y-2Y Treasury Spread"),
    ("DTWEXBGS", "Trade Weighted USD Index"),
    ("INDPRO", "Industrial Production Index"),
    ("RSAFS", "Retail Sales"),
]


class FREDIngester(NewsIngester):
    source_name = "fred"
    source_quality = "primary"

    def __init__(self, session, series: list[tuple[str, str]] | None = None) -> None:
        super().__init__(session)
        self.series = series or FRED_SERIES
        self.api_key = get_settings().fred_api_key

    async def fetch(self) -> AsyncIterator[IngestedItem]:
        if not self.api_key:
            logger.warning("fred_no_api_key")
            return

        async with httpx.AsyncClient(timeout=20.0) as client:
            sem = asyncio.Semaphore(5)
            all_results: list[tuple[str, str, list[dict]]] = []

            async def fetch_series(series_id: str, label: str) -> None:
                async with sem:
                    obs = await self._fetch_observations(client, series_id, limit=10)
                    all_results.append((series_id, label, obs))

            await asyncio.gather(
                *[fetch_series(sid, label) for sid, label in self.series]
            )

        for series_id, label, observations in all_results:
            for obs in observations:
                value = obs.get("value")
                obs_date = obs.get("date")
                if not value or value == "." or not obs_date:
                    continue

                # URL sintetico per dedup deterministico fra run.
                synthetic_url = f"fred://{series_id}/{obs_date}"
                headline = f"{label}: {value} ({obs_date})"

                yield IngestedItem(
                    source=f"fred:{series_id.lower()}",
                    source_quality=self.source_quality,
                    headline=headline,
                    body=None,
                    source_url=synthetic_url,
                    published_at=datetime.fromisoformat(obs_date).replace(tzinfo=UTC),
                    raw_meta={
                        "event_type": "macro_release",
                        "series_id": series_id,
                        "label": label,
                        "value": float(value),
                        "observation_date": obs_date,
                    },
                )

    async def _fetch_observations(
        self, client: httpx.AsyncClient, series_id: str, limit: int = 10
    ) -> list[dict]:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "limit": str(limit),
            "sort_order": "desc",
        }
        try:
            response = await client.get(FRED_OBS_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("fred_fetch_failed", series_id=series_id, error=str(exc))
            return []
        return response.json().get("observations", []) or []
