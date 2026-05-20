"""Scheduler in-process via APScheduler.

Gira nell'event loop del backend FastAPI (lifespan startup) e schedula:
- ingester news/macro a intervalli diversi (gli rss veloci, FRED lento)
- dedup engine che pulisce pending raw_events
- aggiornamento giornaliero prezzi post-close USA

Tutte le task sono asincrone, riusano la SessionLocal del backend. Niente
processo separato → niente Railway service in più → niente costi aggiuntivi.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.agents.calibration import CalibrationAgent
from app.agents.confounder import ConfounderDetector
from app.agents.event_classifier import EventClassifier
from app.agents.expectation import ExpectationEngine
from app.agents.exposure import ExposureEngine
from app.agents.market_reaction import MarketReactionEngine
from app.agents.outcome_tracker import OutcomeTracker
from app.agents.scoring import ScoringEngine
from app.core.db import SessionLocal
from app.ingestion.dedup import DedupEngine
from app.ingestion.finnhub import FinnhubEarningsCalendarIngester, FinnhubNewsIngester
from app.ingestion.fred import FREDIngester
from app.ingestion.polygon_news import PolygonNewsIngester
from app.ingestion.polygon_prices import PolygonPricesIngester
from app.ingestion.rss import RSSIngester
from app.ingestion.sec_edgar import SECEdgarIngester


async def run_rss() -> None:
    async with SessionLocal() as session:
        new = await RSSIngester(session).run()
        logger.info("scheduled_rss_done", new=new)


async def run_polygon_news() -> None:
    async with SessionLocal() as session:
        new = await PolygonNewsIngester(session).run()
        logger.info("scheduled_polygon_news_done", new=new)


async def run_finnhub_news() -> None:
    async with SessionLocal() as session:
        new = await FinnhubNewsIngester(session).run()
        logger.info("scheduled_finnhub_news_done", new=new)


async def run_finnhub_earnings() -> None:
    async with SessionLocal() as session:
        new = await FinnhubEarningsCalendarIngester(session).run()
        logger.info("scheduled_finnhub_earnings_done", new=new)


async def run_sec_edgar() -> None:
    async with SessionLocal() as session:
        new = await SECEdgarIngester(session).run()
        logger.info("scheduled_sec_edgar_done", new=new)


async def run_fred() -> None:
    async with SessionLocal() as session:
        new = await FREDIngester(session).run()
        logger.info("scheduled_fred_done", new=new)


async def run_dedup() -> None:
    async with SessionLocal() as session:
        counts = await DedupEngine(session).process_pending(limit=500)
        logger.info("scheduled_dedup_done", **counts)


async def run_polygon_prices_update() -> None:
    """Aggiorna gli ultimi 3 giorni di prezzi per l'universe."""
    from datetime import date, timedelta

    async with SessionLocal() as session:
        end = date.today()
        start = end - timedelta(days=3)
        results = await PolygonPricesIngester(session).backfill(start=start, end=end)
        total = sum(results.values())
        logger.info("scheduled_prices_update_done", total_bars=total, tickers=len(results))


async def run_classifier() -> None:
    """Classifica i cluster pendenti via Claude Haiku."""
    async with SessionLocal() as session:
        counts = await EventClassifier(session).process_pending(limit=50)
        logger.info("scheduled_classifier_done", **counts)


async def run_expectation_engine() -> None:
    """Calcola expectation per i cluster classificati senza expectation."""
    async with SessionLocal() as session:
        counts = await ExpectationEngine(session).process_pending(limit=30)
        logger.info("scheduled_expectation_done", **counts)


async def run_exposure_engine() -> None:
    """Calcola exposure graph per i cluster classificati."""
    async with SessionLocal() as session:
        counts = await ExposureEngine(session).process_pending(limit=30)
        logger.info("scheduled_exposure_done", **counts)


async def run_market_reaction() -> None:
    """Calcola abnormal return + volume z-score per cluster con exposures."""
    async with SessionLocal() as session:
        counts = await MarketReactionEngine(session).process_pending(limit=50)
        logger.info("scheduled_market_reaction_done", **counts)


async def run_confounder_detector() -> None:
    """Scansiona confounder per cluster classificati."""
    async with SessionLocal() as session:
        counts = await ConfounderDetector(session).process_pending(limit=50)
        logger.info("scheduled_confounder_done", **counts)


async def run_scoring() -> None:
    """Genera impact_score e alert per cluster con expectation+exposure+reaction."""
    async with SessionLocal() as session:
        counts = await ScoringEngine(session).process_pending(limit=50)
        logger.info("scheduled_scoring_done", **counts)


async def run_outcome_tracker() -> None:
    """Aggiorna outcomes per alert con >=1 giorno di età."""
    async with SessionLocal() as session:
        counts = await OutcomeTracker(session).process_pending(limit=100)
        logger.info("scheduled_outcome_done", **counts)


async def run_calibration() -> None:
    """Genera report di calibration (no apply, solo log)."""
    async with SessionLocal() as session:
        report = await CalibrationAgent(session).run()
        logger.info("scheduled_calibration_done", precision=report.get("precision_3d"))


def build_scheduler() -> AsyncIOScheduler:
    """Costruisce lo scheduler con tutti i job registrati. Chiamarlo nel lifespan."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # News ad alta frequenza (~5 min).
    scheduler.add_job(
        run_rss,
        IntervalTrigger(minutes=5),
        id="rss",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        run_polygon_news,
        IntervalTrigger(minutes=5),
        id="polygon_news",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        run_finnhub_news,
        IntervalTrigger(minutes=5),
        id="finnhub_news",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # SEC EDGAR: ogni 10 min (atom feed si aggiorna meno spesso).
    scheduler.add_job(
        run_sec_edgar,
        IntervalTrigger(minutes=10),
        id="sec_edgar",
        max_instances=1,
        coalesce=True,
    )

    # Earnings calendar: 2x al giorno.
    scheduler.add_job(
        run_finnhub_earnings,
        CronTrigger(hour="6,18", minute=15),
        id="finnhub_earnings",
        max_instances=1,
        coalesce=True,
    )

    # FRED macro: ogni 30 min (le serie macro escono al massimo daily).
    scheduler.add_job(
        run_fred,
        IntervalTrigger(minutes=30),
        id="fred",
        max_instances=1,
        coalesce=True,
    )

    # Dedup: ogni 2 min (rapido e tiene la pending queue corta).
    scheduler.add_job(
        run_dedup,
        IntervalTrigger(minutes=2),
        id="dedup",
        max_instances=1,
        coalesce=True,
    )

    # Aggiornamento prezzi: ogni giorno alle 21:30 UTC (post-close USA = 16:30 ET).
    scheduler.add_job(
        run_polygon_prices_update,
        CronTrigger(hour=21, minute=30),
        id="polygon_prices",
        max_instances=1,
        coalesce=True,
    )

    # Phase 2: classifier ogni 5 min (Haiku è veloce, ~$0.001 per cluster).
    scheduler.add_job(
        run_classifier,
        IntervalTrigger(minutes=5),
        id="event_classifier",
        max_instances=1,
        coalesce=True,
    )

    # Phase 3: expectation engine ogni 10 min (alcuni cluster richiedono Sonnet, più caro).
    scheduler.add_job(
        run_expectation_engine,
        IntervalTrigger(minutes=10),
        id="expectation_engine",
        max_instances=1,
        coalesce=True,
    )

    # Phase 4: exposure ogni 7 min (deterministico graph + opzionale Haiku enrichment).
    scheduler.add_job(
        run_exposure_engine,
        IntervalTrigger(minutes=7),
        id="exposure_engine",
        max_instances=1,
        coalesce=True,
    )

    # Phase 5: market reaction ogni 10 min (pura math su prezzi locali).
    scheduler.add_job(
        run_market_reaction,
        IntervalTrigger(minutes=10),
        id="market_reaction",
        max_instances=1,
        coalesce=True,
    )

    # Phase 6: confounder detector ogni 15 min.
    scheduler.add_job(
        run_confounder_detector,
        IntervalTrigger(minutes=15),
        id="confounder_detector",
        max_instances=1,
        coalesce=True,
    )

    # Phase 6: scoring + alert generation ogni 15 min (dopo che gli altri hanno girato).
    scheduler.add_job(
        run_scoring,
        IntervalTrigger(minutes=15),
        id="scoring_engine",
        max_instances=1,
        coalesce=True,
    )

    # Phase 7: outcome tracker ogni 1 ora (orizzonti T+1d/3d/7d/30d).
    scheduler.add_job(
        run_outcome_tracker,
        IntervalTrigger(hours=1),
        id="outcome_tracker",
        max_instances=1,
        coalesce=True,
    )

    # Phase 8: calibration daily a 22:30 UTC (post-update prezzi).
    scheduler.add_job(
        run_calibration,
        CronTrigger(hour=22, minute=30),
        id="calibration",
        max_instances=1,
        coalesce=True,
    )

    logger.info("scheduler_built", jobs=[j.id for j in scheduler.get_jobs()])
    return scheduler
