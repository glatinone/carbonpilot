"""Calculation engine — the deterministic source of truth.

Formula: Activity Data x Emission Factor = kgCO2e

The LLM never produces a carbon number. It calls into this module.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls
from statistics import mean

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.engine.factors import factor_to_dict, resolve_factor
from app.models import Activity, Calculation, Company, EmissionFactor

KG_PER_TONNE = 1000.0


# --------------------------------------------------------------------------- #
# Ingest + calculate
# --------------------------------------------------------------------------- #

def ingest_rows(db: Session, company_id: int, rows: list[dict]) -> dict:
    """Insert activity rows (already mapped to canonical types) and calculate.

    `rows` items: {date, category, activity_type, value, unit, cost, source, meta}
    """
    created = 0
    skipped: list[dict] = []

    company = db.get(Company, company_id)
    region = company.region if company else "WORLD"

    for row in rows:
        try:
            value = float(row["value"])
        except (TypeError, ValueError):
            skipped.append({"row": row, "reason": "value is not numeric"})
            continue
        if value < 0:
            skipped.append({"row": row, "reason": "value is negative"})
            continue

        activity = Activity(
            company_id=company_id,
            date=_as_date(row["date"]),
            category=row.get("category") or "other",
            activity_type=row["activity_type"],
            value=value,
            unit=row.get("unit") or "",
            cost=float(row.get("cost") or 0.0),
            source=row.get("source") or "manual",
            meta=row.get("meta") or {},
        )
        db.add(activity)
        db.flush()

        try:
            factor = resolve_factor(db, activity.activity_type, region)
        except LookupError as exc:
            skipped.append({"row": row, "reason": str(exc)})
            db.delete(activity)
            continue

        db.add(
            Calculation(
                activity_id=activity.id,
                emission_factor_id=factor.id,
                co2e_kg=activity.value * factor.kg_co2e,
                scope=factor.scope,
            )
        )
        created += 1

    db.commit()
    return {"activities_created": created, "rows_skipped": len(skipped), "skipped": skipped[:10]}


def recalculate(db: Session, company_id: int) -> int:
    """Recompute every calculation for a company. Returns rows touched."""
    company = db.get(Company, company_id)
    region = company.region if company else "WORLD"

    rows = db.execute(
        select(Activity, Calculation)
        .join(Calculation, Calculation.activity_id == Activity.id, isouter=True)
        .where(Activity.company_id == company_id)
    ).all()

    touched = 0
    for activity, calc in rows:
        factor = resolve_factor(db, activity.activity_type, region)
        co2e = activity.value * factor.kg_co2e
        if calc is None:
            db.add(
                Calculation(
                    activity_id=activity.id,
                    emission_factor_id=factor.id,
                    co2e_kg=co2e,
                    scope=factor.scope,
                )
            )
        else:
            calc.emission_factor_id = factor.id
            calc.co2e_kg = co2e
            calc.scope = factor.scope
        touched += 1
    db.commit()
    return touched


def _as_date(value) -> date_cls:
    if isinstance(value, date_cls):
        return value
    text = str(value).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m", "%m-%d-%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {value!r}")


# --------------------------------------------------------------------------- #
# Read helpers (all emission values returned in tonnes CO2e)
# --------------------------------------------------------------------------- #

def _joined(db: Session, company_id: int):
    return db.execute(
        select(Activity, Calculation, EmissionFactor)
        .join(Calculation, Calculation.activity_id == Activity.id)
        .join(EmissionFactor, EmissionFactor.id == Calculation.emission_factor_id)
        .where(Activity.company_id == company_id)
    ).all()


def entity_exists(db: Session, company_id: int) -> bool:
    return db.get(Company, company_id) is not None


def baseline(db: Session, company_id: int, year: int | None = None) -> dict:
    rows = _joined(db, company_id)
    if year:
        rows = [r for r in rows if r[0].date.year == year]
    if not rows:
        return {
            "total_tco2e": 0.0,
            "total_cost_usd": 0.0,
            "activity_count": 0,
            "scope_split": {},
            "period": None,
            "incomplete": True,
        }

    total_kg = sum(calc.co2e_kg for _, calc, _ in rows)
    total_cost = sum(act.cost for act, _, _ in rows)
    months = sorted({(act.date.year, act.date.month) for act, _, _ in rows})

    scope_split: dict[str, float] = defaultdict(float)
    for _, calc, _ in rows:
        scope_split[f"scope_{calc.scope}"] += calc.co2e_kg

    month_count = len(months)
    return {
        "total_tco2e": round(total_kg / KG_PER_TONNE, 2),
        "total_cost_usd": round(total_cost, 2),
        "activity_count": len(rows),
        "avg_monthly_tco2e": round(total_kg / KG_PER_TONNE / max(month_count, 1), 2),
        "month_count": month_count,
        "scope_split": {
            k: {"tco2e": round(v / KG_PER_TONNE, 2), "pct": round(100 * v / total_kg, 1)}
            for k, v in sorted(scope_split.items())
        },
        "period": {
            "start": min(m for m in [f"{y}-{mm:02d}" for y, mm in months]),
            "end": max(m for m in [f"{y}-{mm:02d}" for y, mm in months]),
        },
        "incomplete": False,
    }


def breakdown(db: Session, company_id: int, by: str = "category") -> list[dict]:
    rows = _joined(db, company_id)
    total_kg = sum(calc.co2e_kg for _, calc, _ in rows) or 1.0

    buckets: dict[str, dict] = defaultdict(lambda: {"tco2e": 0.0, "cost": 0.0})
    for act, calc, factor in rows:
        key = {
            "category": act.category,
            "activity_type": act.activity_type,
            "scope": f"scope_{calc.scope}",
            "source": factor.source,
        }.get(by, act.category)
        buckets[key]["tco2e"] += calc.co2e_kg
        buckets[key]["cost"] += act.cost

    out = [
        {
            "key": key,
            "tco2e": round(v["tco2e"] / KG_PER_TONNE, 2),
            "cost_usd": round(v["cost"], 2),
            "pct": round(100 * v["tco2e"] / total_kg, 1),
        }
        for key, v in buckets.items()
    ]
    return sorted(out, key=lambda item: item["tco2e"], reverse=True)


def monthly_series(
    db: Session,
    company_id: int,
    activity_type: str | None = None,
    category: str | None = None,
) -> list[dict]:
    rows = _joined(db, company_id)
    buckets: dict[str, dict] = defaultdict(lambda: {"kg": 0.0, "cost": 0.0})

    for act, calc, _ in rows:
        if activity_type and act.activity_type != activity_type:
            continue
        if category and act.category != category:
            continue
        key = f"{act.date.year}-{act.date.month:02d}"
        buckets[key]["kg"] += calc.co2e_kg
        buckets[key]["cost"] += act.cost

    return [
        {
            "month": key,
            "tco2e": round(v["kg"] / KG_PER_TONNE, 3),
            "cost_usd": round(v["cost"], 2),
        }
        for key, v in sorted(buckets.items())
    ]


def period_totals(db: Session, company_id: int, month: str) -> dict:
    """Totals for a single 'YYYY-MM' month, plus per-activity-type detail."""
    rows = [r for r in _joined(db, company_id) if f"{r[0].date.year}-{r[0].date.month:02d}" == month]
    by_type: dict[str, dict] = defaultdict(lambda: {"kg": 0.0, "cost": 0.0, "unit": ""})
    for act, calc, _ in rows:
        by_type[act.activity_type]["kg"] += calc.co2e_kg
        by_type[act.activity_type]["cost"] += act.cost
        by_type[act.activity_type]["unit"] = act.unit

    return {
        "month": month,
        "total_tco2e": round(sum(v["kg"] for v in by_type.values()) / KG_PER_TONNE, 3),
        "total_cost_usd": round(sum(v["cost"] for v in by_type.values()), 2),
        "by_activity_type": {
            k: {
                "tco2e": round(v["kg"] / KG_PER_TONNE, 3),
                "cost_usd": round(v["cost"], 2),
                "unit": v["unit"],
            }
            for k, v in sorted(by_type.items(), key=lambda kv: kv[1]["kg"], reverse=True)
        },
    }


def compare_months(db: Session, company_id: int, month: str, baseline_months: list[str]) -> dict:
    """Compare a month against the mean of baseline months (per activity type)."""
    target = period_totals(db, company_id, month)
    if not baseline_months:
        return {"month": month, "baseline": None, "target": target, "deltas": []}

    baselines = [period_totals(db, company_id, m) for m in baseline_months]
    keys = {k for b in baselines for k in b["by_activity_type"]} | set(target["by_activity_type"])

    deltas = []
    for key in keys:
        base_vals = [b["by_activity_type"].get(key, {}).get("tco2e", 0.0) for b in baselines]
        base_mean = mean(base_vals) if base_vals else 0.0
        target_val = target["by_activity_type"].get(key, {}).get("tco2e", 0.0)
        delta = target_val - base_mean
        pct = (delta / base_mean * 100) if base_mean else 0.0
        deltas.append(
            {
                "activity_type": key,
                "baseline_mean_tco2e": round(base_mean, 3),
                "target_tco2e": round(target_val, 3),
                "delta_tco2e": round(delta, 3),
                "change_pct": round(pct, 1),
            }
        )

    deltas.sort(key=lambda d: abs(d["delta_tco2e"]), reverse=True)
    base_total = mean([b["total_tco2e"] for b in baselines])
    return {
        "month": month,
        "baseline_months": baseline_months,
        "baseline_total_tco2e": round(base_total, 3),
        "target_total_tco2e": target["total_tco2e"],
        "total_change_pct": round(
            ((target["total_tco2e"] - base_total) / base_total * 100) if base_total else 0.0, 1
        ),
        "deltas": deltas,
    }


def emission_factor_trail(db: Session, company_id: int, activity_type: str) -> list[dict]:
    rows = [r for r in _joined(db, company_id) if r[0].activity_type == activity_type]
    seen: dict[int, dict] = {}
    for _, _, factor in rows:
        seen[factor.id] = factor_to_dict(factor)
    return list(seen.values())


def purge_company(db: Session, company_id: int) -> None:
    db.execute(delete(Calculation).where(
        Calculation.activity_id.in_(select(Activity.id).where(Activity.company_id == company_id))
    ))
    db.execute(delete(Activity).where(Activity.company_id == company_id))
    db.commit()
