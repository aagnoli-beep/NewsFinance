from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SourceQuality(StrEnum):
    OFFICIAL = "official"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SOCIAL = "social"
    RUMOR = "rumor"


class EventType(StrEnum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    CONTRACT = "contract"
    MA = "m_and_a"
    REGULATORY = "regulatory"
    MACRO_DATA = "macro_data"
    CENTRAL_BANK = "central_bank"
    GEOPOLITICAL = "geopolitical"
    PRODUCT = "product"
    CLINICAL_TRIAL = "clinical_trial"
    LITIGATION = "litigation"
    PERSONNEL = "personnel"
    ANALYST_RATING = "analyst_rating"
    OTHER = "other"


class SurpriseDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class SurpriseMagnitude(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExposureType(StrEnum):
    DIRECT = "direct"
    PEER = "peer"
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    ETF = "etf"
    COMMODITY = "commodity"
    COUNTRY = "country"
    SECTOR = "sector"


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_quality: Mapped[SourceQuality] = mapped_column(
        String(16), default=SourceQuality.SECONDARY
    )
    url_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    headline: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="SET NULL"), nullable=True, index=True
    )

    cluster: Mapped["EventCluster | None"] = relationship(back_populates="raw_events")


class EventCluster(Base):
    __tablename__ = "event_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[EventType] = mapped_column(String(32), index=True)
    headline_canonical: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    raw_events: Mapped[list[RawEvent]] = relationship(back_populates="cluster")
    expectations: Mapped[list["Expectation"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )
    exposures: Mapped[list["Exposure"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )
    event_entities: Mapped[list["EventEntity"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )


class EventClusterMember(Base):
    """Junction kept for explicit M2M history if a raw event ever links to multiple clusters."""

    __tablename__ = "event_cluster_members"

    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), primary_key=True
    )
    raw_event_id: Mapped[int] = mapped_column(
        ForeignKey("raw_events.id", ondelete="CASCADE"), primary_key=True
    )
    similarity: Mapped[float] = mapped_column(Float, default=1.0)


class EventEntity(Base):
    __tablename__ = "event_entities"

    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), default="mentioned")

    cluster: Mapped[EventCluster] = relationship(back_populates="event_entities")


class Expectation(Base):
    __tablename__ = "expectations"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), unique=True
    )
    baseline_source: Mapped[str] = mapped_column(String(64))
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    surprise_direction: Mapped[SurpriseDirection] = mapped_column(String(16))
    surprise_magnitude: Mapped[SurpriseMagnitude] = mapped_column(String(16))
    surprise_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cluster: Mapped[EventCluster] = relationship(back_populates="expectations")


class Exposure(Base):
    __tablename__ = "exposures"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), index=True
    )
    asset_ticker: Mapped[str] = mapped_column(String(32), index=True)
    exposure_type: Mapped[ExposureType] = mapped_column(String(32))
    hop_distance: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    cluster: Mapped[EventCluster] = relationship(back_populates="exposures")

    __table_args__ = (
        UniqueConstraint("cluster_id", "asset_ticker", name="uq_exposure_cluster_ticker"),
        Index("ix_exposures_ticker", "asset_ticker"),
    )
