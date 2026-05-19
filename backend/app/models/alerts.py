from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OutcomeLabel(StrEnum):
    CONFIRMED_DIRECTION = "confirmed_direction"
    REVERSED = "reversed"
    FLAT = "flat"
    CONFOUNDED = "confounded"
    PENDING = "pending"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey("event_clusters.id", ondelete="CASCADE"), unique=True, index=True
    )
    impact_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    explanation_md: Mapped[str] = mapped_column(Text)
    components: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), unique=True, index=True
    )
    t_plus_1d_ar: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_plus_3d_ar: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_plus_7d_ar: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_plus_30d_ar: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_label: Mapped[OutcomeLabel] = mapped_column(String(32), default=OutcomeLabel.PENDING)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
