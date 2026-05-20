"""Calibration agent — analizza outcomes degli alert recenti e suggerisce
modifiche a pesi/soglie.

Per ora NON applica automaticamente. Logga raccomandazioni in modo leggibile;
sarà l'utente a decidere se modificare WEIGHTS in scoring.py.

Metriche di partenza:
- precision = confirmed_direction / (confirmed_direction + reversed)
- coverage = total_alerts / total_classified_clusters (quanti eventi
  classificati passano la soglia)
- decay precision a 1d/3d/7d (per regimi diversi)

Output: log strutturato + tabella riepilogativa.
"""

from __future__ import annotations

from collections import Counter

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alerts import Alert, Outcome
from app.models.events import EventCluster

WINDOW_DAYS = 30


class CalibrationAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self) -> dict:
        cutoff = func.now() - func.make_interval(0, 0, 0, WINDOW_DAYS)

        # Alert nella finestra
        alerts_q = select(Alert.id, Alert.created_at, Alert.impact_score).where(
            Alert.created_at >= cutoff
        )
        alerts = (await self.session.execute(alerts_q)).all()
        n_alerts = len(alerts)

        # Outcome dei suddetti alert
        outcomes_q = (
            select(Outcome.outcome_label, Outcome.t_plus_1d_ar, Outcome.t_plus_3d_ar)
            .join(Alert, Alert.id == Outcome.alert_id)
            .where(Alert.created_at >= cutoff)
        )
        outcomes = (await self.session.execute(outcomes_q)).all()
        outcome_counter: Counter[str] = Counter([o[0] for o in outcomes])

        confirmed = outcome_counter.get("confirmed_direction", 0)
        reversed_ = outcome_counter.get("reversed", 0)
        flat = outcome_counter.get("flat", 0)
        confounded = outcome_counter.get("confounded", 0)
        pending = outcome_counter.get("pending", 0)

        precision_3d = (
            confirmed / (confirmed + reversed_) if (confirmed + reversed_) > 0 else None
        )

        # Total clusters classificati nella finestra
        total_clusters_q = (
            select(func.count())
            .select_from(EventCluster)
            .where(EventCluster.created_at >= cutoff)
            .where(EventCluster.event_type != "unclassified")
        )
        total_clusters = (await self.session.execute(total_clusters_q)).scalar() or 0

        coverage = n_alerts / total_clusters if total_clusters else None

        report = {
            "window_days": WINDOW_DAYS,
            "total_classified_clusters": total_clusters,
            "alerts_generated": n_alerts,
            "alert_rate": round(coverage, 3) if coverage is not None else None,
            "outcomes": {
                "confirmed_direction": confirmed,
                "reversed": reversed_,
                "flat": flat,
                "confounded": confounded,
                "pending": pending,
            },
            "precision_3d": round(precision_3d, 3) if precision_3d is not None else None,
            "recommendations": self._build_recommendations(
                precision_3d, coverage, n_alerts
            ),
        }

        logger.info("calibration_report", **report)
        return report

    @staticmethod
    def _build_recommendations(
        precision: float | None, coverage: float | None, n_alerts: int
    ) -> list[str]:
        recs: list[str] = []
        if n_alerts < 5:
            recs.append("Sample troppo piccolo (<5 alert valutati). Aspetta più dati prima di calibrare.")
            return recs
        if precision is not None:
            if precision < 0.5:
                recs.append(
                    "Precision <50%: considera ridurre w_novelty / w_source e aumentare "
                    "w_confirm; soglia alert potrebbe essere troppo bassa."
                )
            elif precision >= 0.7:
                recs.append(
                    "Precision >=70%: gli alert sono affidabili. Considera abbassare "
                    "soglia (0.65 → 0.60) per più copertura."
                )
        if coverage is not None:
            if coverage > 0.2:
                recs.append(
                    f"Alert rate alto ({coverage:.0%}): troppo rumore? "
                    "Valuta alzare la soglia (0.65 → 0.70)."
                )
            elif coverage < 0.02:
                recs.append(
                    f"Alert rate basso ({coverage:.0%}): troppi falsi negativi? "
                    "Valuta abbassare la soglia o aumentare w_exposure."
                )
        if not recs:
            recs.append("Nessuna calibrazione necessaria sulla base dei dati attuali.")
        return recs
