from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class EntityType(StrEnum):
    COMPANY = "company"
    PERSON = "person"
    COUNTRY = "country"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    ETF = "etf"
    INDEX = "index"
    SECTOR = "sector"
    CENTRAL_BANK = "central_bank"
    INDUSTRY_TERM = "industry_term"


class LinkType(StrEnum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    PEER = "peer"
    SUBSIDIARY = "subsidiary"
    ETF_HOLDING = "etf_holding"
    COMMODITY_EXPOSURE = "commodity_exposure"
    COUNTRY_EXPOSURE = "country_exposure"


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[EntityType] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    ticker: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    lei: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    outgoing_links: Mapped[list["EntityLink"]] = relationship(
        back_populates="from_entity",
        foreign_keys="EntityLink.from_entity_id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_entities_name_lower", func.lower(name)),)


class EntityLink(Base):
    __tablename__ = "entity_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    to_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    link_type: Mapped[LinkType] = mapped_column(String(32))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    llm_suggested: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    from_entity: Mapped[Entity] = relationship(
        foreign_keys=[from_entity_id], back_populates="outgoing_links"
    )
    to_entity: Mapped[Entity] = relationship(foreign_keys=[to_entity_id])

    __table_args__ = (
        UniqueConstraint("from_entity_id", "to_entity_id", "link_type", name="uq_link_triple"),
        Index("ix_entity_links_from", "from_entity_id"),
        Index("ix_entity_links_to", "to_entity_id"),
    )
