"""Scenario engine — the "what if we change this?" hero feature.

Two entry points:
  * `run_scenario`        — apply explicit interventions, return estimated impact
  * `find_feasible`       — constraint search: "cut 15% carbon without raising cost"

All arithmetic is deterministic; the LLM only orchestrates and explains.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.calculator import KG_PER_TONNE, baseline
from app.models import Activity, Calculation, EmissionFactor

EFFORT_SCORE = {"low": 1.0, "medium": 0.6, "high": 0.3}


@dataclass
class Intervention:
    """A change applied to one activity type.

    reduction_pct     : share of the activity removed (0-100)
    cost_delta_pct    : change in that activity's cost as a share of its annual cost.
                        -30 means a 30% saving; +20 means a 20% investment premium.
    """

    activity_type: str
    reduction_pct: float
    cost_delta_pct: float = 0.0
    title: str = ""
    effort: str = "medium"
    confidence_pct: float = 80.0

    def to_dict(self) -> dict:
        return asdict(self)


def _annual_by_type(db: Session, company_id: int) -> dict[str, dict]:
    """Annual tCO2e, cost and factor detail per activity type."""
    rows = db.execute(
        select(Activity, Calculation, EmissionFactor)
        .join(Calculation, Calculation.activity_id == Activity.id)
        .join(EmissionFactor, EmissionFactor.id == Calculation.emission_factor_id)
        .where(Activity.company_id == company_id)
    ).all()

    out: dict[str, dict] = defaultdict(
        lambda: {"kg": 0.0, "cost": 0.0, "uncertainty": 0.0, "months": set(), "scope": 3}
    )
    for act, calc, factor in rows:
        bucket = out[act.activity_type]
        bucket["kg"] += calc.co2e_kg
        bucket["cost"] += act.cost
        bucket["uncertainty"] = factor.uncertainty_pct
        bucket["months"].add(f"{act.date.year}-{act.date.month:02d}")
        bucket["scope"] = calc.scope

    return {
        k: {
            "tco2e": v["kg"] / KG_PER_TONNE,
            "cost_usd": v["cost"],
            "uncertainty_pct": v["uncertainty"],
            "month_count": len(v["months"]),
            "scope": v["scope"],
        }
        for k, v in out.items()
    }


def _confidence(uncertainty_pct: float, month_count: int) -> float:
    """Lower confidence when the factor is uncertain or the history is short."""
    confidence = 97.0 - 0.55 * uncertainty_pct - max(0, 6 - month_count) * 3.0
    return round(max(40.0, min(97.0, confidence)), 1)


def candidate_catalog(db: Session, company_id: int) -> list[Intervention]:
    """Build the menu of credible interventions from the company's own data."""
    annual = _annual_by_type(db, company_id)
    candidates: list[Intervention] = []

    def add(activity_type: str, reduction: float, cost_delta: float, title: str, effort: str):
        if activity_type not in annual:
            return
        candidates.append(
            Intervention(
                activity_type=activity_type,
                reduction_pct=reduction,
                cost_delta_pct=cost_delta,
                title=title,
                effort=effort,
                confidence_pct=_confidence(
                    annual[activity_type]["uncertainty_pct"], annual[activity_type]["month_count"]
                ),
            )
        )

    add("cloud_compute_vcpu_hour", 30, -30, "Right-size weekend cloud workloads", "medium")
    add("cloud_compute_vcpu_hour", 55, -45, "Move batch compute to a greener region", "high")
    add("cloud_storage_gb_month", 20, -18, "Lifecycle-tier cold storage archives", "low")
    add("electricity_kwh", 15, -15, "Office energy efficiency retrofit", "low")
    add("electricity_kwh", 80, 20, "Renewable PPA for purchased electricity", "high")
    add("flight_passenger_km", 25, -25, "Shift internal travel to virtual meetings", "low")
    add("flight_passenger_km", 45, -30, "Mandate rail over short-haul flights", "medium")
    add("diesel_litre", 40, 15, "Electrify the delivery fleet", "high")
    add("diesel_litre", 12, -8, "Driver efficiency and route optimisation", "low")
    add("petrol_litre", 35, 15, "Electrify the sales fleet", "high")
    add("procurement_usd", 10, -2, "Supplier engagement and low-carbon sourcing", "medium")
    add("waste_landfill_kg", 30, -6, "Waste diversion and recycling programme", "low")
    add("water_m3", 15, -4, "Water efficiency fixtures", "low")
    add("natural_gas_kwh", 20, -12, "Boiler tuning and heat recovery", "medium")
    add("hotel_night", 10, -10, "Sustainable-hotel travel policy", "low")
    add("car_km", 20, -15, "Car-pooling and EV hire policy", "medium")

    return [c for c in candidates if annual.get(c.activity_type, {}).get("tco2e", 0) > 0]


def run_scenario(
    db: Session,
    company_id: int,
    interventions: list[dict],
    label: str | None = None,
) -> dict:
    """Simulate interventions against a freshly read baseline."""
    return _scenario_from(
        baseline(db, company_id), _annual_by_type(db, company_id), interventions, label
    )


def _scenario_from(
    base: dict,
    annual: dict,
    interventions: list[dict],
    label: str | None = None,
) -> dict:
    """Pure scenario maths over an already-read baseline.

    Neither ``base`` nor ``annual`` depends on the interventions, so the caller
    reads them once. The constraint search evaluates thousands of combinations
    and would otherwise re-aggregate the entire activity history for every one
    of them — the difference between a snappy demo and 30 seconds of dead air.
    """
    per_intervention = []
    total_tco2e_cut = 0.0
    total_cost_delta = 0.0
    months_covered = max([v["month_count"] for v in annual.values()], default=12) or 12
    # Report annualised figures so a partial history is still comparable.
    annualise = 12.0 / months_covered

    for item in interventions:
        activity_type = item.get("activity_type")
        if activity_type not in annual:
            per_intervention.append(
                {
                    "activity_type": activity_type,
                    "error": f"No activity data for {activity_type!r} — intervention skipped.",
                }
            )
            continue

        reduction_pct = float(item.get("reduction_pct", 0.0))
        cost_delta_pct = float(item.get("cost_delta_pct", item.get("cost_delta", 0.0)))
        detail = annual[activity_type]

        baseline_t = detail["tco2e"] * annualise
        baseline_cost = detail["cost_usd"] * annualise

        cut_t = baseline_t * reduction_pct / 100.0
        cost_delta = baseline_cost * cost_delta_pct / 100.0

        total_tco2e_cut += cut_t
        total_cost_delta += cost_delta

        per_intervention.append(
            {
                "activity_type": activity_type,
                "title": item.get("title") or activity_type.replace("_", " ").title(),
                "reduction_pct": reduction_pct,
                "cost_delta_pct": cost_delta_pct,
                "baseline_tco2e": round(baseline_t, 2),
                "baseline_cost_usd": round(baseline_cost, 2),
                "carbon_saving_tco2e": round(cut_t, 2),
                "cost_delta_usd": round(cost_delta, 2),
                "effort": item.get("effort", "medium"),
                "confidence_pct": item.get("confidence_pct"),
            }
        )

    projected_tco2e = max(0.0, base["total_tco2e"] - total_tco2e_cut)
    projected_cost = base["total_cost_usd"] + total_cost_delta
    pct_carbon = (total_tco2e_cut / base["total_tco2e"] * 100) if base["total_tco2e"] else 0.0

    assumptions = [
        "Reductions apply uniformly across the activity type; no rebound effect is modelled.",
        "Emission factors are held constant across the scenario horizon.",
        f"Annualised from {months_covered} month(s) of recorded activity data.",
        "Financial impact is limited to the activity's own cost line, not capex or financing.",
    ]

    return {
        "label": label or "Scenario",
        "baseline": {
            "total_tco2e": base["total_tco2e"],
            "total_cost_usd": base["total_cost_usd"],
        },
        "projected": {
            "total_tco2e": round(projected_tco2e, 2),
            "total_cost_usd": round(projected_cost, 2),
        },
        "impact": {
            "carbon_saving_tco2e": round(total_tco2e_cut, 2),
            "carbon_reduction_pct": round(pct_carbon, 1),
            "cost_delta_usd": round(total_cost_delta, 2),
            "cost_direction": (
                "saving" if total_cost_delta < 0 else "increase" if total_cost_delta > 0 else "neutral"
            ),
        },
        "per_intervention": per_intervention,
        "assumptions": assumptions,
        "is_estimate": True,
    }


def find_feasible(
    db: Session,
    company_id: int,
    min_carbon_reduction_pct: float = 10.0,
    max_cost_increase_usd: float = 0.0,
    max_interventions: int = 4,
    limit: int = 5,
) -> dict:
    """Constraint search: find intervention sets that satisfy a carbon floor
    without exceeding a cost ceiling.

    This is the "AI negotiates trade-offs" signature feature.
    """
    catalog = candidate_catalog(db, company_id)
    if not catalog:
        return {
            "constraints": {
                "min_carbon_reduction_pct": min_carbon_reduction_pct,
                "max_cost_increase_usd": max_cost_increase_usd,
            },
            "scenarios_evaluated": 0,
            "feasible": [],
            "infeasible": [],
            "message": "No candidate interventions available — ingest activity data first.",
            "message_key": "sim.searchNoCatalog",
            "feasible_count": 0,
            "infeasible_count": 0,
        }

    # One variant per activity type keeps the search space tractable and stops
    # contradictory double-counting (e.g. -30% and -55% on the same stream).
    by_type: dict[str, list[Intervention]] = defaultdict(list)
    for cand in catalog:
        by_type[cand.activity_type].append(cand)

    evaluated: list[dict] = []
    types = sorted(by_type)

    # Read once: neither the baseline nor the per-type annuals depend on which
    # combination is being evaluated, and this loop runs thousands of times.
    base = baseline(db, company_id)
    annual = _annual_by_type(db, company_id)

    for size in range(1, min(max_interventions, len(types)) + 1):
        for combo_types in combinations(types, size):
            for variants in _variant_product([by_type[t] for t in combo_types]):
                result = _scenario_from(
                    base, annual, [v.to_dict() for v in variants], label=_label(variants)
                )
                impact = result["impact"]
                feasible = (
                    impact["carbon_reduction_pct"] >= min_carbon_reduction_pct
                    and impact["cost_delta_usd"] <= max_cost_increase_usd
                )
                evaluated.append(
                    {
                        "label": result["label"],
                        "interventions": [
                            {
                                "activity_type": v.activity_type,
                                "title": v.title,
                                "reduction_pct": v.reduction_pct,
                                "effort": v.effort,
                            }
                            for v in variants
                        ],
                        "carbon_reduction_pct": impact["carbon_reduction_pct"],
                        "carbon_saving_tco2e": impact["carbon_saving_tco2e"],
                        "cost_delta_usd": impact["cost_delta_usd"],
                        "projected_tco2e": result["projected"]["total_tco2e"],
                        "effort": _worst_effort(variants),
                        "confidence_pct": round(
                            sum(v.confidence_pct for v in variants) / len(variants), 1
                        ),
                        "feasible": feasible,
                    }
                )

    feasible = [e for e in evaluated if e["feasible"]]
    infeasible = [e for e in evaluated if not e["feasible"]]

    # Best = meets the constraint with the most carbon reduction per dollar spent.
    feasible.sort(
        key=lambda e: (
            e["carbon_reduction_pct"],
            -e["cost_delta_usd"],
        ),
        reverse=True,
    )
    infeasible.sort(
        key=lambda e: (
            abs(e["carbon_reduction_pct"] - min_carbon_reduction_pct)
            + abs(e["cost_delta_usd"] - max_cost_increase_usd) / 1000.0
        )
    )

    chosen = feasible[0] if feasible else None
    # Structured rather than prose only, like _neighbour_note: the counts and a
    # message key travel, and the wording is chosen per language at render time
    # because the UI is bilingual. The English `message` stays on the payload —
    # the agent reads this result as tool data, and consumers that predate the
    # key must keep working unchanged.
    feasible_count = len(feasible)
    return {
        "constraints": {
            "min_carbon_reduction_pct": min_carbon_reduction_pct,
            "max_cost_increase_usd": max_cost_increase_usd,
            "max_interventions": max_interventions,
        },
        "scenarios_evaluated": len(evaluated),
        "feasible": feasible[:limit],
        "infeasible": infeasible[:limit],
        "recommended": chosen,
        "message": (
            f"{feasible_count} of {len(evaluated)} evaluated scenarios satisfy both constraints."
            if feasible_count
            else (
                f"No scenario satisfies both constraints ({len(evaluated)} evaluated). "
                "Closest alternatives are listed under infeasible."
            )
        ),
        "message_key": "sim.searchFeasible" if feasible_count else "sim.searchInfeasible",
        "feasible_count": feasible_count,
        "infeasible_count": len(infeasible),
    }


def _variant_product(options: list[list[Intervention]]):
    from itertools import product

    yield from product(*options)


def _label(variants: list[Intervention] | tuple) -> str:
    parts = [f"{v.title} ({v.reduction_pct:.0f}%)" for v in variants]
    return " + ".join(parts) if parts else "Empty scenario"


def _worst_effort(variants) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return max((v.effort for v in variants), key=lambda e: order.get(e, 1), default="low")
