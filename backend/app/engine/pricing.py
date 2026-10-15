"""Carbon pricing engine — the cost of a tonne is a decision input, not an afterthought.

Exactly one number comes into this module (the price per tonne, typed by a human)
and everything else is recomputed by the same deterministic rules the rest of the
app uses. No LLM participates: the price multiplies stored calculations, and the
verdict is a machine-chosen sentence assembled from structured data so the UI can
render it in either language.

Verdict logic (deliberately simple, therefore auditable):

* price == 0  -> the ranked list is the financial ranking only (cost_impact_usd
  ascending); the verdict names that state.
* price > 0   -> each action gets a net financial position
  net_usd = cost_impact_usd + (carbon_impact_t * price)
  (a negative cost_impact_usd is a saving; a saved tonne is worth price dollars).
  Actions are re-ranked by net_usd ascending, then by score descending as a
  deterministic tiebreak. The verdict compares the new leader with the old one.

The re-ranking is the point: at a high carbon price the cheapest abatement stops
being the most attractive and the biggest-tonnage actions surface, which is how a
CFO reads a marginal abatement cost curve.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.engine import calculator, recommender

MIN_PRICE_USD = 0.0


@dataclass
class PricedAction:
    """A recommendation re-valued under an explicit carbon price."""

    id: int
    title: str
    activity_type: str
    carbon_impact_t: float
    cost_impact_usd: float
    effort: str
    confidence_pct: float
    score: float
    # Net position:
    carbon_value_usd: float  # carbon_impact_t * price (positive = avoided cost)
    net_usd: float  # cost_impact_usd + carbon_value_usd
    rank_financial: int  # rank by cost_impact_usd alone (price == 0 ordering)
    rank_priced: int  # rank by net_usd at this price


def price_scenario(
    db: Session, company_id: int, price_usd_per_t: float
) -> dict:
    """Re-value the whole footprint and the action catalog at one carbon price."""
    price = max(float(price_usd_per_t), MIN_PRICE_USD)

    base = calculator.baseline(db, company_id)
    if base.get("incomplete"):
        return {
            "company_id": company_id,
            "price_usd_per_t": price,
            "baseline_total_tco2e": 0.0,
            "annual_carbon_cost_usd": 0.0,
            "action_count": 0,
            "actions": [],
            "verdict_key": "pricing.empty",
            "verdict_vars": {},
        }

    total_tco2e = base["total_tco2e"]
    annual_carbon_cost_usd = round(total_tco2e * price, 2)

    recs = recommender.list_all(db, company_id) or recommender.generate(
        db, company_id, replace=True
    )

    by_financial = sorted(recs, key=lambda r: (r.cost_impact_usd, -r.score))
    financial_rank = {r.id: i + 1 for i, r in enumerate(by_financial)}

    priced: list[PricedAction] = []
    for r in recs:
        carbon_value_usd = r.carbon_impact_t * price
        net_usd = r.cost_impact_usd + carbon_value_usd
        priced.append(
            PricedAction(
                id=r.id,
                title=r.title,
                activity_type=r.activity_type,
                carbon_impact_t=r.carbon_impact_t,
                cost_impact_usd=r.cost_impact_usd,
                effort=r.effort,
                confidence_pct=r.confidence_pct,
                score=r.score,
                carbon_value_usd=carbon_value_usd,
                net_usd=net_usd,
                rank_financial=financial_rank[r.id],
                rank_priced=1,  # provisional, replaced below
            )
        )

    priced.sort(key=lambda a: (round(a.net_usd, 2), -a.score))
    for index, action in enumerate(priced):
        action.rank_priced = index + 1

    actions = [
        {
            "id": a.id,
            "title": a.title,
            "activity_type": a.activity_type,
            "carbon_impact_t": round(a.carbon_impact_t, 2),
            "cost_impact_usd": round(a.cost_impact_usd, 2),
            "effort": a.effort,
            "confidence_pct": a.confidence_pct,
            "carbon_value_usd": round(a.carbon_value_usd, 2),
            "net_usd": round(a.net_usd, 2),
            "rank_financial": a.rank_financial,
            "rank_priced": a.rank_priced,
        }
        for a in priced
    ]

    return {
        "company_id": company_id,
        "price_usd_per_t": price,
        "baseline_total_tco2e": round(total_tco2e, 2),
        "annual_carbon_cost_usd": annual_carbon_cost_usd,
        "action_count": len(actions),
        "actions": actions,
        "verdict_key": _verdict_key(priced, actions, price),
        "verdict_vars": _verdict_vars(priced, actions, price),
    }


def _verdict_key(priced: list[PricedAction], actions: list[dict], price: float) -> str:
    if not priced:
        return "pricing.empty"
    if price <= MIN_PRICE_USD:
        return "pricing.financialOnly"
    leader = priced[0]
    if leader.net_usd < 0:
        return "pricing.paysForItself"
    return "pricing.stillCosts"


def _verdict_vars(
    priced: list[PricedAction], actions: list[dict], price: float
) -> dict:
    """The numbers a UI needs to render a sentence per language for each verdict."""
    if not priced:
        return {"price": round(price, 2)}
    leader = priced[0]
    previous_leader = next(
        (a for a in priced if a.rank_financial == 1 and a.id != leader.id), None
    )
    return {
        "price": round(price, 2),
        "leader_title": leader.title,
        "leader_net_usd": round(leader.net_usd, 2),
        "leader_carbon_value_usd": round(leader.carbon_value_usd, 2),
        "leader_tonnage": round(leader.carbon_impact_t, 1),
        "old_leader_title": previous_leader.title if previous_leader else None,
        "old_net_usd": round(previous_leader.net_usd, 2) if previous_leader else None,
        "action_count": len(priced),
    }
