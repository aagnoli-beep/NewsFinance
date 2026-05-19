from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    interval: Mapped[str] = mapped_column(String(8), default="1d")

    __table_args__ = (
        UniqueConstraint("ticker", "ts", "interval", name="uq_price_ticker_ts_interval"),
        Index("ix_prices_ticker_ts", "ticker", "ts"),
    )


class MarketReaction(Base):
    __tablename__ = "market_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), index=True
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    pre_event_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_15m: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    abnormal_return_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    abnormal_return_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    peer_avg_ar: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_confirmation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("cluster_id", "ticker", name="uq_reaction_cluster_ticker"),
    )


class Confounder(Base):
    __tablename__ = "confounders"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), index=True
    )
    confounding_cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE")
    )
    materiality_score: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint("cluster_id", "confounding_cluster_id", name="uq_confounder_pair"),
    )
