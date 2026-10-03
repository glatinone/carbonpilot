"""Tool layer exposed to the Gemini agent.

Every tool is a thin wrapper over the deterministic engines. The agent decides
*which* tool to call; the tool decides the number. Each function returns plain
JSON so the result can be handed straight back to the model and also streamed
to the UI as an audit trail.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine import anomaly, calculator, factors, recommender, scenario
from app.models import ActionItem, Recommendation

# --------------------------------------------------------------------------- #
# Tool implementations
# --------------------------------------------------------------------------- #

def tool_get_baseline(db: Session, company_id: int) -> dict:
    """Total footprint, cost, and the Scope 1/2/3 split."""
    return calculator.baseline(db, company_id)


def tool_get_emission_breakdown(db: Session, company_id: int, by: str = "category") -> dict:
    """Break the footprint down by category, activity type, or scope."""
    by = by if by in {"category", "activity_type", "scope"} else "category"
    rows = calculator.breakdown(db, company_id, by=by)
    return {"by": by, "rows": rows[:15]}


def tool_get_monthly_series(
    db: Session, company_id: int, activity_type: str | None = None, category: str | None = None
) -> dict:
    """Month-by-month emissions for the whole company or one activity type."""
    series = calculator.monthly_series(db, company_id, activity_type, category)
    return {
        "activity_type": activity_type,
        "category": category,
        "points": series,
        "months": len(series),
    }


def tool_compare_month(db: Session, company_id: int, month: str) -> dict:
    """Compare one YYYY-MM month against the preceding six months."""
    months = [p["month"] for p in calculator.monthly_series(db, company_id)]
    try:
        idx = months.index(month)
    except ValueError:
        return {
            "error": f"Month {month!r} not found.",
            "available_months": months,
        }
    baseline_months = [m for m in months[max(0, idx - 6): idx] if m != month][-6:]
    result = calculator.compare_months(db, company_id, month, baseline_months)
    result["deltas"] = result["deltas"][:10]
    return result


def tool_detect_anomalies(
    db: Session, company_id: int, activity_type: str | None = None, z_threshold: float = 3.0
) -> dict:
    """Statistical outliers in the monthly emission series (median/MAD, robust)."""
    found = anomaly.detect(db, company_id, z_threshold=z_threshold, activity_type=activity_type)
    return {"count": len(found), "anomalies": found[:10]}


def tool_explain_anomaly(db: Session, company_id: int, month: str, activity_type: str) -> dict:
    """Evidence trail behind an anomaly: what moved, by how much, and why."""
    result = anomaly.explain(db, company_id, month, activity_type)
    return {
        "month": result["month"],
        "activity_type": result["activity_type"],
        "baseline_months": result["baseline_months"],
        "total_change_pct": result["comparison"].get("total_change_pct"),
        "activity_change": result["target_detail"],
        "drivers": result["drivers"],
        "top_movers": result["comparison"]["deltas"][:5],
    }


def tool_run_scenario(db: Session, company_id: int, interventions: list[dict]) -> dict:
    """Simulate explicit interventions, e.g. reduce cloud compute by 30%."""
    return scenario.run_scenario(db, company_id, interventions)


def tool_find_feasible_scenarios(
    db: Session,
    company_id: int,
    min_carbon_reduction_pct: float = 10.0,
    max_cost_increase_usd: float = 0.0,
) -> dict:
    """Search for intervention sets that meet a carbon target within a cost ceiling."""
    return scenario.find_feasible(
        db,
        company_id,
        min_carbon_reduction_pct=min_carbon_reduction_pct,
        max_cost_increase_usd=max_cost_increase_usd,
    )


def tool_search_emission_factors(db: Session, company_id: int, query: str) -> dict:
    """Look up the emission factor library, including its citation and uncertainty."""
    found = factors.search_factors(db, query)
    return {"query": query, "count": len(found), "factors": [factors.factor_to_dict(f) for f in found]}


def tool_search_methodology(db: Session, company_id: int, query: str, k: int = 4) -> dict:
    """Retrieve the methodology passages that back a claim.

    The factor library answers "what number was used"; this answers "why is that
    number defensible" — GHG Protocol scope rules, spend-based caveats, grid and
    conversion-factor sources, cloud methodology, uncertainty treatment. Without
    it the model would explain methodology from its own recollection.
    """
    from app.engine import retrieval

    passages = retrieval.search(query, k=max(1, min(int(k), 8)))
    return {
        "query": query,
        "count": len(passages),
        "passages": [
            {
                "source": p["source"],
                "section": p["section"],
                "topic": p["topic"],
                "text": p["text"],
                "score": p["score"],
            }
            for p in passages
        ],
    }


def tool_list_recommendations(db: Session, company_id: int) -> dict:
    """Ranked decarbonisation actions (carbon x cost x effort), best first."""
    from app.engine.recommender import generate

    recs = recommender.list_all(db, company_id)
    if not recs:
        recs = generate(db, company_id, replace=True)
    return {"count": len(recs), "recommendations": [recommender.to_dict(r) for r in recs[:10]]}


def tool_create_action(
    db: Session, company_id: int, recommendation_id: int, owner: str = "Unassigned"
) -> dict:
    """Turn an approved recommendation into an owned, tracked action item."""
    rec = db.get(Recommendation, recommendation_id)
    if not rec or rec.company_id != company_id:
        return {"error": f"Recommendation {recommendation_id} not found for this company."}

    # Idempotent, for the same reason the HTTP route is: the plan sums every
    # tracked action, so a second approval must not double-count the impact.
    existing = db.scalar(
        select(ActionItem).where(
            ActionItem.company_id == company_id,
            ActionItem.recommendation_id == rec.id,
        )
    )
    if existing is not None:
        rec.status = "approved"
        db.commit()
        db.refresh(existing)
        return _action_payload(existing, already_tracked=True)

    action = ActionItem(
        company_id=company_id,
        recommendation_id=rec.id,
        owner=owner,
        task=rec.title,
        expected_carbon_t=rec.carbon_impact_t,
        expected_cost_usd=rec.cost_impact_usd,
        status="open",
    )
    db.add(action)
    rec.status = "approved"
    db.commit()
    db.refresh(action)

    return _action_payload(action)


def _action_payload(action: ActionItem, already_tracked: bool = False) -> dict:
    payload = {
        "action_id": action.id,
        "owner": action.owner,
        "task": action.task,
        "expected_carbon_t": action.expected_carbon_t,
        "expected_cost_usd": action.expected_cost_usd,
        "status": action.status,
    }
    if already_tracked:
        payload["note"] = "This recommendation already has a tracked action; returning it."
    return payload


# --------------------------------------------------------------------------- #
# Registry + Gemini function declarations
# --------------------------------------------------------------------------- #

TOOLS: dict[str, dict[str, Any]] = {
    "get_baseline": {
        "fn": tool_get_baseline,
        "description": "Get the company's total carbon footprint in tCO2e, total cost, and the Scope 1/2/3 split.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "get_emission_breakdown": {
        "fn": tool_get_emission_breakdown,
        "description": "Break total emissions down by category, activity_type, or scope.",
        "parameters": {
            "type": "object",
            "properties": {
                "by": {
                    "type": "string",
                    "description": "Dimension to break down by.",
                    "enum": ["category", "activity_type", "scope"],
                }
            },
            "required": [],
        },
    },
    "get_monthly_series": {
        "fn": tool_get_monthly_series,
        "description": "Month-by-month emissions and cost, optionally filtered to one activity type or category.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_type": {"type": "string", "description": "e.g. cloud_compute_vcpu_hour"},
                "category": {"type": "string", "description": "e.g. cloud, electricity, travel, fleet"},
            },
            "required": [],
        },
    },
    "compare_month": {
        "fn": tool_compare_month,
        "description": "Compare a YYYY-MM month against the preceding six months, with per-activity-type deltas.",
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Month in YYYY-MM format, e.g. 2026-05"}
            },
            "required": ["month"],
        },
    },
    "detect_anomalies": {
        "fn": tool_detect_anomalies,
        "description": "Find statistical anomalies in the monthly emission series using a robust median/MAD z-score.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_type": {"type": "string", "description": "Optional: restrict to one activity type."},
                "z_threshold": {"type": "number", "description": "Sensitivity; default 3.0."},
            },
            "required": [],
        },
    },
    "explain_anomaly": {
        "fn": tool_explain_anomaly,
        "description": "Explain WHY an anomaly happened: baseline comparison plus attributed drivers (e.g. weekend share shift).",
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Month in YYYY-MM format."},
                "activity_type": {"type": "string", "description": "Activity type to explain."},
            },
            "required": ["month", "activity_type"],
        },
    },
    "run_scenario": {
        "fn": tool_run_scenario,
        "description": "Simulate what-if interventions and return estimated carbon, financial impact and assumptions.",
        "parameters": {
            "type": "object",
            "properties": {
                "interventions": {
                    "type": "array",
                    "description": "List of interventions to apply together.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "activity_type": {"type": "string"},
                            "reduction_pct": {"type": "number", "description": "0-100"},
                            "cost_delta_pct": {
                                "type": "number",
                                "description": "Negative = saving, positive = investment premium. Defaults to 0.",
                            },
                        },
                        "required": ["activity_type", "reduction_pct"],
                    },
                }
            },
            "required": ["interventions"],
        },
    },
    "find_feasible_scenarios": {
        "fn": tool_find_feasible_scenarios,
        "description": (
            "Constraint search. Given a minimum carbon reduction and a maximum cost increase, "
            "enumerate intervention combinations and return which ones satisfy both constraints."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min_carbon_reduction_pct": {"type": "number", "description": "Required carbon cut, e.g. 15"},
                "max_cost_increase_usd": {
                    "type": "number",
                    "description": "Cost ceiling in USD/year. 0 means no increase allowed; negative means must save money.",
                },
            },
            "required": ["min_carbon_reduction_pct"],
        },
    },
    "search_emission_factors": {
        "fn": tool_search_emission_factors,
        "description": "Search the emission factor library for a source, unit, scope and uncertainty figure.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "e.g. 'electricity', 'flight', 'cloud'"}},
            "required": ["query"],
        },
    },
    "search_methodology": {
        "fn": tool_search_methodology,
        "description": (
            "Retrieve the carbon-accounting methodology passages behind a claim: GHG Protocol scope "
            "definitions, Scope 2 location vs market based, spend-based Scope 3 caveats, grid and "
            "conversion-factor sources, Cloud Carbon Footprint method, uncertainty propagation, and "
            "robust spike detection. Call this whenever you explain HOW a figure was derived or which "
            "scope/method applies, then cite the returned source and section."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What needs grounding, e.g. 'why is spend-based procurement uncertain'.",
                },
                "k": {
                    "type": "integer",
                    "description": "How many passages to return. Default 4, maximum 8.",
                },
            },
            "required": ["query"],
        },
    },
    "list_recommendations": {
        "fn": tool_list_recommendations,
        "description": "List ranked decarbonisation actions with carbon impact, cost impact, effort and confidence.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "create_action": {
        "fn": tool_create_action,
        "description": "Create a tracked action item from an approved recommendation.",
        "parameters": {
            "type": "object",
            "properties": {
                "recommendation_id": {"type": "integer"},
                "owner": {"type": "string", "description": "Team or person who owns the action."},
            },
            "required": ["recommendation_id"],
        },
    },
}


def tool_names() -> list[str]:
    return list(TOOLS)


def dispatch(db: Session, company_id: int, name: str, args: dict | None = None) -> dict:
    """Execute a tool by name. Always returns a dict (errors included, never raises)."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"Unknown tool {name!r}. Available: {', '.join(TOOLS)}"}
    fn: Callable = spec["fn"]
    try:
        return fn(db, company_id, **(args or {}))
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - surfaced to the model as data
        return {"error": f"{name} failed: {exc}"}


def summarize(name: str, result: dict) -> str:
    """One-line trace entry for the UI audit trail."""
    if "error" in result:
        return f"{name}: {result['error']}"
    if name == "get_baseline":
        return f"baseline {result.get('total_tco2e')} tCO2e over {result.get('month_count')} months"
    if name == "detect_anomalies":
        return f"{result.get('count', 0)} anomaly(ies) detected"
    if name == "explain_anomaly":
        return f"explained {result.get('activity_type')} in {result.get('month')}"
    if name == "run_scenario":
        impact = result.get("impact", {})
        return f"scenario: -{impact.get('carbon_saving_tco2e')} tCO2e, {impact.get('cost_delta_usd')} USD"
    if name == "find_feasible_scenarios":
        return f"{len(result.get('feasible', []))} feasible scenario(s)"
    if name == "list_recommendations":
        return f"{result.get('count', 0)} recommendation(s)"
    if name == "create_action":
        return f"action #{result.get('action_id')} for {result.get('owner')}"
    if name == "search_emission_factors":
        return f"{result.get('count', 0)} factor(s) for {result.get('query')!r}"
    if name == "search_methodology":
        top = (result.get("passages") or [{}])[0]
        return (
            f"{result.get('count', 0)} methodology passage(s); "
            f"top = {top.get('source')} — {top.get('section')}"
        )
    if name == "compare_month":
        if "error" in result:
            return f"compare_month: {result['error']}"
        return (
            f"{result.get('month')} vs prior months: {result.get('total_change_pct')}% "
            f"({result.get('target_total_tco2e')} tCO2e)"
        )
    if name == "get_monthly_series":
        return f"{len(result.get('points', []))} monthly point(s)"
    if name == "get_emission_breakdown":
        top = (result.get("rows") or [{}])[0]
        return f"broken down by {result.get('by')}; top = {top.get('key')} ({top.get('pct')}%)"
    return name
