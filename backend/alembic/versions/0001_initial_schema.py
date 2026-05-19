"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("lei", sa.String(length=20), nullable=True),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index("ix_entities_type", "entities", ["type"])
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_ticker", "entities", ["ticker"])
    op.create_index("ix_entities_lei", "entities", ["lei"])
    op.create_index("ix_entities_isin", "entities", ["isin"])
    op.create_index("ix_entities_name_lower", "entities", [sa.text("lower(name)")])

    op.create_table(
        "entity_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "from_entity_id",
            sa.Integer(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_entity_id",
            sa.Integer(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("link_type", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("llm_suggested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("from_entity_id", "to_entity_id", "link_type", name="uq_link_triple"),
    )
    op.create_index("ix_entity_links_from", "entity_links", ["from_entity_id"])
    op.create_index("ix_entity_links_to", "entity_links", ["to_entity_id"])

    op.create_table(
        "event_clusters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("headline_canonical", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("novelty_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_event_clusters_first_seen", "event_clusters", ["first_seen"])
    op.create_index("ix_event_clusters_event_type", "event_clusters", ["event_type"])
    op.execute(
        "CREATE INDEX ix_event_clusters_embedding ON event_clusters "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "raw_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_quality", sa.String(length=16), nullable=False, server_default="secondary"),
        sa.Column("url_hash", sa.String(length=64), nullable=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("raw_meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("url_hash"),
    )
    op.create_index("ix_raw_events_source", "raw_events", ["source"])
    op.create_index("ix_raw_events_url_hash", "raw_events", ["url_hash"])
    op.create_index("ix_raw_events_published_at", "raw_events", ["published_at"])
    op.create_index("ix_raw_events_ingested_at", "raw_events", ["ingested_at"])
    op.create_index("ix_raw_events_cluster", "raw_events", ["cluster_id"])

    op.create_table(
        "event_cluster_members",
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "raw_event_id",
            sa.Integer(),
            sa.ForeignKey("raw_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("similarity", sa.Float(), nullable=False, server_default="1.0"),
    )

    op.create_table(
        "event_entities",
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entity_id",
            sa.Integer(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="mentioned"),
    )

    op.create_table(
        "expectations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("baseline_source", sa.String(length=64), nullable=False),
        sa.Column("expected_value", sa.Text(), nullable=True),
        sa.Column("actual_value", sa.Text(), nullable=True),
        sa.Column("surprise_direction", sa.String(length=16), nullable=False),
        sa.Column("surprise_magnitude", sa.String(length=16), nullable=False),
        sa.Column("surprise_zscore", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("cluster_id"),
    )

    op.create_table(
        "exposures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_ticker", sa.String(length=32), nullable=False),
        sa.Column("exposure_type", sa.String(length=32), nullable=False),
        sa.Column("hop_distance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.UniqueConstraint("cluster_id", "asset_ticker", name="uq_exposure_cluster_ticker"),
    )
    op.create_index("ix_exposures_cluster", "exposures", ["cluster_id"])
    op.create_index("ix_exposures_ticker", "exposures", ["asset_ticker"])

    op.create_table(
        "prices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("interval", sa.String(length=8), nullable=False, server_default="1d"),
        sa.UniqueConstraint("ticker", "ts", "interval", name="uq_price_ticker_ts_interval"),
    )
    op.create_index("ix_prices_ticker_ts", "prices", ["ticker", "ts"])
    op.create_index("ix_prices_ticker", "prices", ["ticker"])
    op.create_index("ix_prices_ts", "prices", ["ts"])

    op.create_table(
        "market_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("pre_event_price", sa.Float(), nullable=True),
        sa.Column("price_15m", sa.Float(), nullable=True),
        sa.Column("price_1h", sa.Float(), nullable=True),
        sa.Column("price_1d", sa.Float(), nullable=True),
        sa.Column("price_3d", sa.Float(), nullable=True),
        sa.Column("abnormal_return_1d", sa.Float(), nullable=True),
        sa.Column("abnormal_return_3d", sa.Float(), nullable=True),
        sa.Column("volume_zscore", sa.Float(), nullable=True),
        sa.Column("peer_avg_ar", sa.Float(), nullable=True),
        sa.Column("market_confirmation", sa.String(length=16), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("cluster_id", "ticker", name="uq_reaction_cluster_ticker"),
    )
    op.create_index("ix_market_reactions_cluster", "market_reactions", ["cluster_id"])
    op.create_index("ix_market_reactions_ticker", "market_reactions", ["ticker"])

    op.create_table(
        "confounders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "confounding_cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("materiality_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("rationale", sa.String(length=512), nullable=True),
        sa.UniqueConstraint(
            "cluster_id", "confounding_cluster_id", name="uq_confounder_pair"
        ),
    )
    op.create_index("ix_confounders_cluster", "confounders", ["cluster_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cluster_id",
            sa.Integer(),
            sa.ForeignKey("event_clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation_md", sa.Text(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("cluster_id"),
    )
    op.create_index("ix_alerts_cluster", "alerts", ["cluster_id"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    op.create_table(
        "outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "alert_id",
            sa.Integer(),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("t_plus_1d_ar", sa.Float(), nullable=True),
        sa.Column("t_plus_3d_ar", sa.Float(), nullable=True),
        sa.Column("t_plus_7d_ar", sa.Float(), nullable=True),
        sa.Column("t_plus_30d_ar", sa.Float(), nullable=True),
        sa.Column("outcome_label", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("alert_id"),
    )
    op.create_index("ix_outcomes_alert", "outcomes", ["alert_id"])


def downgrade() -> None:
    op.drop_table("outcomes")
    op.drop_table("alerts")
    op.drop_table("confounders")
    op.drop_table("market_reactions")
    op.drop_table("prices")
    op.drop_table("exposures")
    op.drop_table("expectations")
    op.drop_table("event_entities")
    op.drop_table("event_cluster_members")
    op.drop_table("raw_events")
    op.execute("DROP INDEX IF EXISTS ix_event_clusters_embedding")
    op.drop_table("event_clusters")
    op.drop_table("entity_links")
    op.drop_table("entities")
