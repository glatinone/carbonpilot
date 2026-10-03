"""Dashboard + insight endpoints. All numbers come from the calculation engine."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import anomaly, calculator, recommender
from app.engine.scenario import candidate_catalog
from app.models import Company

router = APIRouter(prefix="/api", tags=["dashboard"])


def require_company(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")
    return company


@router.get("/companies")
def list_companies(db: Session = Depends(get_db)) -> list[dict]:
    from sqlalchemy import select

    return [
        {"id": c.id, "name": c.name, "region": c.region}
        for c in db.scalars(select(Company).order_by(Company.id)).all()
    ]


@router.get("/dashboard")
def dashboard(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    company = require_company(db, company_id)

    base = calculator.baseline(db, company_id)
    monthly = calculator.monthly_series(db, company_id)
    anomalies = anomaly.detect(db, company_id)

    insights = _build_insights(db, company_id, anomalies)
    recs = recommender.list_all(db, company_id) or recommender.generate(db, company_id, True)

    # Month-over-month trend for the hero card.
    trend_pct = None
    if len(monthly) >= 2:
        prev, last = monthly[-2]["tco2e"], monthly[-1]["tco2e"]
        if prev:
            trend_pct = round((last - prev) / prev * 100, 1)

    return {
        "company": {"id": company.id, "name": company.name, "region": company.region},
        "baseline": base,
        "trend_pct": trend_pct,
        "breakdown": calculator.breakdown(db, company_id, by="category"),
        "breakdown_by_activity": calculator.breakdown(db, company_id, by="activity_type"),
        "series": monthly,
        "anomalies": anomalies,
        "insights": insights,
        "recommendations": [recommender.to_dict(r) for r in recs[:6]],
        "opportunity_count": len(recs),
        "llm_enabled": _llm_enabled(),
    }


@router.get("/baseline")
def baseline(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    require_company(db, company_id)
    return calculator.baseline(db, company_id)


@router.get("/breakdown")
def breakdown(
    company_id: int = Query(1),
    by: str = Query("category", pattern="^(category|activity_type|scope)$"),
    db: Session = Depends(get_db),
) -> dict:
    require_company(db, company_id)
    return {"by": by, "rows": calculator.breakdown(db, company_id, by=by)}


@router.get("/series")
def series(
    company_id: int = Query(1),
    activity_type: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    require_company(db, company_id)
    return {
        "points": calculator.monthly_series(db, company_id, activity_type, category),
        "activity_type": activity_type,
        "category": category,
    }


@router.get("/anomalies")
def anomalies(
    company_id: int = Query(1),
    z_threshold: float = Query(3.0, ge=1.0, le=10.0),
    db: Session = Depends(get_db),
) -> dict:
    require_company(db, company_id)
    found = anomaly.detect(db, company_id, z_threshold=z_threshold)
    return {"count": len(found), "anomalies": found}


@router.get("/anomalies/explain")
def explain(
    month: str,
    activity_type: str,
    company_id: int = Query(1),
    db: Session = Depends(get_db),
) -> dict:
    require_company(db, company_id)
    return anomaly.explain(db, company_id, month, activity_type)


@router.get("/insights")
def insights(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    require_company(db, company_id)
    found = _build_insights(db, company_id, anomaly.detect(db, company_id))
    return {"count": len(found), "insights": found}


@router.get("/interventions")
def interventions(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    """The menu of credible interventions derived from this company's own data."""
    require_company(db, company_id)
    catalog = candidate_catalog(db, company_id)
    return {
        "count": len(catalog),
        "interventions": [
            {
                "activity_type": c.activity_type,
                "title": c.title,
                "reduction_pct": c.reduction_pct,
                "cost_delta_pct": c.cost_delta_pct,
                "effort": c.effort,
                "confidence_pct": c.confidence_pct,
            }
            for c in catalog
        ],
    }


# --------------------------------------------------------------------------- #

def _build_insights(db: Session, company_id: int, anomalies: list[dict]) -> list[dict]:
    """Turn raw anomalies into decision-ready cards with an attributed driver."""
    from app.engine.scenario import candidate_catalog, run_scenario

    catalog = candidate_catalog(db, company_id)
    insights: list[dict] = []

    for item in anomalies[:5]:
        activity_type = item["activity_type"]
        if activity_type == "all":
            continue

        detail = anomaly.explain(db, company_id, item["month"], activity_type)
        matching = [c for c in catalog if c.activity_type == activity_type]
        intervention = matching[0] if matching else None

        impact_t = 0.0
        impact_cost = 0.0
        confidence = 70.0
        if intervention:
            result = run_scenario(db, company_id, [intervention.to_dict()])
            impact_t = result["impact"]["carbon_saving_tco2e"]
            impact_cost = result["impact"]["cost_delta_usd"]
            confidence = intervention.confidence_pct

        driver_text = (
            detail["drivers"][0]["description"]
            if detail.get("drivers")
            else "No single driver isolated — review the contributing activity rows."
        )

        insights.append(
            {
                "headline": (
                    f"{activity_type.replace('_', ' ').title()} "
                    f"{'spiked' if item['direction'] == 'spike' else 'dropped'} "
                    f"{abs(item['change_pct']):.0f}% in {item['month']}"
                ),
                "detail": driver_text,
                "activity_type": activity_type,
                "month": item["month"],
                "carbon_impact_t": round(impact_t, 2),
                "cost_impact_usd": round(impact_cost, 2),
                "confidence_pct": round(confidence, 1),
                "evidence": {
                    "observed_tco2e": item["value_tco2e"],
                    "baseline_tco2e": item["baseline_tco2e"],
                    "delta_tco2e": item["delta_tco2e"],
                    "change_pct": item["change_pct"],
                    "z_score": item["z_score"],
                    "severity": item["severity"],
                    "baseline_months": detail.get("baseline_months", []),
                    "suggested_action": intervention.title if intervention else None,
                },
            }
        )

    return insights


def _llm_enabled() -> bool:
    from app.config import get_settings

    return get_settings().llm_enabled
