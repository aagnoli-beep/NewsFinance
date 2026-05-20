"""Schemi Pydantic per l'output strutturato degli agenti LLM."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Tipologie entità che possiamo tracciare nell'event graph.
EntityType = Literal[
    "company",
    "person",
    "country",
    "commodity",
    "currency",
    "etf",
    "sector",
    "central_bank",
    "industry_term",
]


# Allineato con EventType in app.models.events.
EVENT_TYPE_VALUES = [
    "earnings",
    "guidance",
    "contract",
    "m_and_a",
    "regulatory",
    "macro_data",
    "central_bank",
    "geopolitical",
    "product",
    "clinical_trial",
    "litigation",
    "personnel",
    "analyst_rating",
    "buyback",
    "dividend",
    "partnership",
    "layoffs",
    "bankruptcy",
    "other",
]


class ClassifiedEntity(BaseModel):
    """Un'entità estratta dal testo dell'evento."""

    name: str = Field(description="Nome ufficiale dell'entità (es. 'Apple Inc.', 'Federal Reserve', 'Brent crude')")
    type: EntityType
    ticker: str | None = Field(default=None, description="Solo se company quotata su mercato USA o ETF noto")
    role: Literal["primary", "mentioned"] = Field(
        description="primary se l'evento è direttamente su questa entità; mentioned se contestuale"
    )


class ClassifiedEvent(BaseModel):
    """Output dell'event classifier per un singolo cluster."""

    event_type: Literal[
        "earnings",
        "guidance",
        "contract",
        "m_and_a",
        "regulatory",
        "macro_data",
        "central_bank",
        "geopolitical",
        "product",
        "clinical_trial",
        "litigation",
        "personnel",
        "analyst_rating",
        "buyback",
        "dividend",
        "partnership",
        "layoffs",
        "bankruptcy",
        "other",
    ]
    entities: list[ClassifiedEntity] = Field(default_factory=list, max_length=12)
    sentiment: Literal["positive", "negative", "neutral"] = "neutral"
    novelty_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = routine/duplicato, 0.5 = normale, 1.0 = evento materiale unico",
    )
    summary: str = Field(
        max_length=300,
        description="Riassunto neutro in una frase (italiano o inglese a seconda della fonte)",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidenza del classifier nella decisione",
    )


class ExpectationResult(BaseModel):
    """Output dell'expectation engine per un singolo cluster."""

    baseline_source: Literal[
        "finnhub_consensus",
        "fred_prior_release",
        "trading_economics_consensus",
        "llm_inference_from_prior_news",
        "no_baseline",
    ]
    expected_value: str | None = Field(
        default=None, description="Cosa il mercato si aspettava (valore o frase breve)"
    )
    actual_value: str | None = Field(
        default=None, description="Cosa è successo realmente (valore o frase breve)"
    )
    surprise_direction: Literal["positive", "negative", "neutral", "uncertain"]
    surprise_magnitude: Literal["low", "medium", "high"]
    surprise_zscore: float | None = Field(
        default=None,
        description="Z-score numerico solo se calcolabile (es. earnings beat/miss vs std consensus)",
    )
    rationale: str = Field(
        max_length=500,
        description="Spiegazione del perché di questa classificazione di sorpresa",
    )
