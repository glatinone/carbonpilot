"""Target trajectory engine — the cost of a commitment, computed.

A target is stated the way boards state it: "cut X% by year Y". The engine draws
the linear glide from today's footprint to that target and prices every year of the
path at a carbon price, so the cost of the commitment is visible year by year.

Deterministic by construction: the reduction applies linearly over the years
between now and the target year, and carbon cost is tonnes x price. No LLM
produces any of these numbers.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.engine import calculator


def project_trajectory(
    db: Session,
    company_id: int,
    target_reduction_pct: float,
    target_year: int,
    price_usd_per_t: float = 50.0,
) -> dict:
    """Linear path from today's footprint to a % reduction by a target year.

    `years` covers current_year..target_year inclusive; `projected_tco2e` is the
    linear interpolation at each year (year 0 = baseline, last year = target).
    `carbon_cost_usd` = projected tonnes x price, so the cost of the commitment
    is visible per year at a single human-supplied carbon price.
    """
    base = calculator.baseline(db, company_id)
    if base.get("incomplete"):
        return {
            "company_id": company_id,
            "baseline_total_tco2e": 0.0,
            "target_total_tco2e": 0.0,
            "years": [],
            "price_usd_per_t": price_usd_per_t,
            "note": "No baseline — load activity data first.",
        }

    baseline_total = base["total_tco2e"]
    target_total = baseline_total * (1 - target_reduction_pct / 100.0)
    current_year = date.today().year
    total_years = max(target_year - current_year, 1)

    years = []
    for index, year in enumerate(range(current_year, target_year + 1)):
        progress = index / total_years
        projected = baseline_total * (1 - (target_reduction_pct / 100.0) * progress)
        years.append(
            {
                "year": year,
                "projected_tco2e": round(projected, 2),
                "carbon_cost_usd": round(projected * price_usd_per_t, 2),
            }
        )

    return {
        "company_id": company_id,
        "baseline_total_tco2e": round(baseline_total, 2),
        "target_total_tco2e": round(target_total, 2),
        "target_reduction_pct": target_reduction_pct,
        "target_year": target_year,
        "price_usd_per_t": price_usd_per_t,
        "years": years,
        "note": None,
    }
