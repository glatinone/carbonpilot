"""Recommendation engine — turns hotspots and anomalies into ranked actions.

Every recommendation answers four questions a sustainability manager actually
gets asked by management:
  * what should we do?
  * how much carbon does it save?
  * what does it cost (or save)?
  * how confident are we, and why?
"""

from __future__ import annotations

import math

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.engine.anomaly import detect, explain
from app.engine.calculator import baseline, breakdown
from app.engine.scenario import EFFORT_SCORE, candidate_catalog, run_scenario
from app.models import Recommendation

W_CARBON = 0.5
W_COST = 0.3
W_EFFORT = 0.2

# Financial impact is log-scaled. A linear scale saturates instantly: a $10k
# saving and a $3M saving would both clamp to "maximum", so a 7-tonne policy
# tweak would tie a 66-tonne engineering project.
COST_LOG_SCALE_USD = 1_000.0
COST_LOG_DIVISOR = 3.0


def _cost_norm(cost_delta_usd: float) -> float:
    """-1 (expensive) .. +1 (big saving), compressing three orders of magnitude."""
    if cost_delta_usd == 0:
        return 0.0
    magnitude = math.log10(1 + abs(cost_delta_usd) / COST_LOG_SCALE_USD) / COST_LOG_DIVISOR
    magnitude = min(1.0, magnitude)
    return -magnitude if cost_delta_usd > 0 else magnitude


def _action_score(carbon_t: float, cost_delta_usd: float, effort: str, confidence: float,
                  max_carbon: float) -> float:
    """0-100 operational priority score.

    Deliberately not "biggest carbon number wins": a modest reduction that is
    cheap and easy to ship should beat a large one that is expensive and hard.
    """
    carbon_norm = carbon_t / max_carbon if max_carbon else 0.0
    effort_norm = EFFORT_SCORE.get(effort, 0.6)
    raw = (W_CARBON * carbon_norm) + (W_COST * _cost_norm(cost_delta_usd)) + (W_EFFORT * effort_norm)
    return round(max(0.0, raw) * (confidence / 100.0) * 100.0, 1)


def generate(db: Session, company_id: int, replace: bool = True) -> list[Recommendation]:
    base = baseline(db, company_id)
    if base.get("incomplete"):
        return []

    catalog = candidate_catalog(db, company_id)
    if not catalog:
        return []

    breakdown_rows = breakdown(db, company_id, by="activity_type")
    by_type = {row["key"]: row for row in breakdown_rows}

    # Only propose the strongest variant per activity type plus any anomalous one.
    anomalies = detect(db, company_id)
    anomaly_types = {a["activity_type"] for a in anomalies}

    scenarios: list[dict] = []
    for candidate in catalog:
        if candidate.activity_type in anomaly_types:
            # Under an anomaly, the recoverable volume is what was excess.
            scenarios.append(run_scenario(db, company_id, [candidate.to_dict()]))
        scenarios.append(run_scenario(db, company_id, [candidate.to_dict()]))

    # Deduplicate identical intervention sets.
    seen: set[tuple] = set()
    unique: list[dict] = []
    for result in scenarios:
        key = tuple(
            sorted(
                (i["activity_type"], round(i["reduction_pct"], 1))
                for i in result["per_intervention"]
                if "error" not in i
            )
        )
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(result)

    max_carbon = max(
        (
            item["impact"]["carbon_saving_tco2e"]
            for result in unique
            for item in [result]
            if result["impact"]["carbon_saving_tco2e"] > 0
        ),
        default=1.0,
    ) or 1.0

    if replace:
        db.execute(delete(Recommendation).where(Recommendation.company_id == company_id))

    created: list[Recommendation] = []
    for result in unique:
        intervention = next((i for i in result["per_intervention"] if "error" not in i), None)
        if not intervention:
            continue

        activity_type = intervention["activity_type"]
        carbon_t = result["impact"]["carbon_saving_tco2e"]
        cost_delta = result["impact"]["cost_delta_usd"]
        effort = intervention.get("effort", "medium")
        confidence = intervention.get("confidence_pct") or 75.0
        catalog_entry = next(c for c in catalog if c.activity_type == activity_type
                             and abs(c.reduction_pct - intervention["reduction_pct"]) < 0.01)

        share_pct = by_type.get(activity_type, {}).get("pct", 0.0)
        evidence = {
            "activity_type": activity_type,
            "share_of_footprint_pct": share_pct,
            "baseline_tco2e": intervention["baseline_tco2e"],
            "baseline_cost_usd": intervention["baseline_cost_usd"],
            "method": "activity_data x emission_factor",
            "assumptions": result["assumptions"],
            "unit": "tCO2e/year (annualised)",
        }

        if activity_type in anomaly_types:
            anomaly = next((a for a in anomalies if a["activity_type"] == activity_type), None)
            evidence["anomaly"] = anomaly
            evidence["driver"] = explain(
                db, company_id, anomaly["month"], activity_type
            ).get("drivers", [])

        created.append(
            Recommendation(
                company_id=company_id,
                title=catalog_entry.title,
                description=(
                    f"Apply a {intervention['reduction_pct']:.0f}% reduction to "
                    f"{activity_type.replace('_', ' ')} "
                    f"({share_pct:.0f}% of the current footprint)."
                ),
                category=activity_type.split("_")[0],
                activity_type=activity_type,
                carbon_impact_t=round(carbon_t, 2),
                cost_impact_usd=round(cost_delta, 2),
                effort=effort,
                confidence_pct=confidence,
                evidence=evidence,
                score=_action_score(carbon_t, cost_delta, effort, confidence, max_carbon),
                status="proposed",
            )
        )

    created.sort(key=lambda r: r.score, reverse=True)
    for recommendation in created:
        db.add(recommendation)
    db.commit()

    # Refresh to pick up generated ids.
    return list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.company_id == company_id)
            .order_by(Recommendation.score.desc())
        ).all()
    )


def list_all(db: Session, company_id: int) -> list[Recommendation]:
    return list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.company_id == company_id)
            .order_by(Recommendation.score.desc())
        ).all()
    )


def to_dict(rec: Recommendation) -> dict:
    return {
        "id": rec.id,
        "title": rec.title,
        "description": rec.description,
        "activity_type": rec.activity_type,
        "carbon_impact_t": rec.carbon_impact_t,
        "cost_impact_usd": rec.cost_impact_usd,
        "effort": rec.effort,
        "confidence_pct": rec.confidence_pct,
        "score": rec.score,
        "status": rec.status,
        "evidence": rec.evidence,
    }
