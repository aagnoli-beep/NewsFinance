import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.clusters import router as clusters_router
from app.api.coverage import router as coverage_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info("NewsFinance backend starting", env=settings.env)

    scheduler = None
    # WORKER_ENABLED=false per disabilitare lo scheduler in dev/test.
    if os.getenv("WORKER_ENABLED", "true").lower() == "true":
        from app.worker.scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
        logger.info("scheduler_started")

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
    logger.info("NewsFinance backend shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="NewsFinance API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(events_router, prefix="/api")
    app.include_router(coverage_router, prefix="/api")
    app.include_router(clusters_router, prefix="/api")

    return app


app = create_app()
