"""Anomaly detection on monthly emission series.

Robust z-score (median / MAD) rather than mean/stddev, because a single spike
inflates the standard deviation and hides itself. MAD is immune to that.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.calculator import KG_PER_TONNE, monthly_series, period_totals
from app.models import Activity

MAD_SCALE = 0.6745  # makes MAD comparable to a standard deviation
DEFAULT_Z_THRESHOLD = 3.0
# A company-wide total always wiggles; only call it an anomaly if it actually moved.
AGGREGATE_MIN_CHANGE_PCT = 10.0


def _mad(values: list[float], center: float) -> float:
    if not values:
        return 0.0
    return median([abs(v - center) for v in values])


def detect(
    db: Session,
    company_id: int,
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    activity_type: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Return anomalies sorted by severity (largest absolute delta first)."""
    series = monthly_series(db, company_id, activity_type=activity_type, category=category)
    if len(series) < 4:
        return []

    points = {p["month"]: p["tco2e"] for p in series}
    values = list(points.values())
    center = median(values)
    mad = _mad(values, center)
    scale = mad / MAD_SCALE if mad > 0 else None

    if scale is None:
        # Degenerate series (flat, or one dominant value): fall back to mean/std.
        from statistics import pstdev

        spread = pstdev(values)
        if spread == 0:
            return []
        scale = spread

    anomalies: list[dict] = []
    for month, value in sorted(points.items()):
        z = (value - center) / scale if scale else 0.0
        if abs(z) < z_threshold:
            continue
        delta = value - center
        anomalies.append(
            {
                "month": month,
                "activity_type": activity_type or category or "all",
                "value_tco2e": round(value, 3),
                "baseline_tco2e": round(center, 3),
                "delta_tco2e": round(delta, 3),
                "change_pct": round((delta / center * 100) if center else 0.0, 1),
                "z_score": round(z, 2),
                "direction": "spike" if delta > 0 else "drop",
                "severity": "high" if abs(z) >= 4 else "medium",
            }
        )

    # Optionally split by activity type too, to catch a spike hidden inside a
    # flat category total. The company-level series is noisy by construction
    # (it aggregates unrelated streams), so it needs a materiality floor.
    if activity_type is None and category is None:
        anomalies = [a for a in anomalies if abs(a["change_pct"]) >= AGGREGATE_MIN_CHANGE_PCT]
        per_type = _detect_per_activity_type(db, company_id, z_threshold)
        known = {a["month"] for a in anomalies}
        for item in per_type:
            if item["month"] not in known:
                anomalies.append(item)

    anomalies.sort(key=lambda a: abs(a["delta_tco2e"]), reverse=True)
    return anomalies


def _detect_per_activity_type(db: Session, company_id: int, z_threshold: float) -> list[dict]:
    from sqlalchemy import select

    types = db.scalars(
        select(Activity.activity_type).where(Activity.company_id == company_id).distinct()
    ).all()

    results: list[dict] = []
    for activity_type in types:
        for item in detect(db, company_id, z_threshold, activity_type=activity_type):
            results.append(item)
    return results


def explain(db: Session, company_id: int, month: str, activity_type: str) -> dict:
    """Build the evidence trail behind an anomaly ("why did this happen?")."""
    from app.engine.calculator import compare_months

    months = [p["month"] for p in monthly_series(db, company_id)]
    try:
        idx = months.index(month)
    except ValueError:
        idx = len(months) - 1
    baseline_months = [m for m in months[max(0, idx - 6) : idx] if m != month][-6:]

    comparison = compare_months(db, company_id, month, baseline_months)
    detail = next(
        (d for d in comparison["deltas"] if d["activity_type"] == activity_type), None
    )

    # Driver analysis from activity metadata (e.g. weekend share of cloud usage).
    rows = db.execute(
        select(Activity.meta, Activity.value).where(
            Activity.company_id == company_id,
            Activity.activity_type == activity_type,
        )
    ).all()

    meta_by_month: dict[str, list[float]] = defaultdict(list)
    for meta, _value in rows:
        if not meta:
            continue
        key = meta.get("month")
        if key:
            meta_by_month[key].append(float(meta.get("weekend_share", 0.0)))

    drivers: list[dict] = []
    if meta_by_month:
        base_shares = [
            v for m, vals in meta_by_month.items() if m in baseline_months for v in vals
        ]
        target_shares = meta_by_month.get(month, [])
        if base_shares and target_shares:
            base_share = sum(base_shares) / len(base_shares)
            target_share = sum(target_shares) / len(target_shares)
            if target_share > base_share + 0.05:
                ratio = (target_share / base_share) if base_share else 0.0
                drivers.append(
                    {
                        "driver": "weekend_share",
                        "description": (
                            f"Weekend share of {activity_type} usage rose from "
                            f"{base_share:.0%} to {target_share:.0%} "
                            f"({ratio:.1f}x the previous baseline)."
                        ),
                        "baseline": round(base_share, 3),
                        "observed": round(target_share, 3),
                        "ratio": round(ratio, 2),
                    }
                )

    return {
        "month": month,
        "activity_type": activity_type,
        "baseline_months": baseline_months,
        "comparison": comparison,
        "target_detail": detail,
        "drivers": drivers,
    }
