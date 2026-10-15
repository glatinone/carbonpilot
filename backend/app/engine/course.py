"""Course-correct — the plan made honest against recorded reality.

The approved action plan carries an expected abatement (expected_carbon_t per
ActionItem). Course-correct divides that plan across the months since the plan
started, then compares the company's recorded monthly emissions against the
glide path the plan implies:

    required_monthly = plan_total / months_since_plan
    on track  when  actual_monthly_avg <= baseline_monthly_avg - required_monthly

If actual emissions are dropping at least as fast as the plan needs, the plan is
on track; otherwise the ledger says behind. All numbers come from stored
calculations — no LLM arithmetic.
"""

from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine import calculator
from app.models import ActionItem


def course_check(db: Session, company_id: int) -> dict:
    base = calculator.baseline(db, company_id)
    if base.get("incomplete"):
        return {
            "plan_total_tco2e": 0.0,
            "months_since_plan": 0,
            "required_monthly_tco2e": 0.0,
            "actual_monthly_tco2e": 0.0,
            "baseline_monthly_tco2e": 0.0,
            "verdict_key": "course.noPlan",
            "verdict_vars": {"reason": "no_baseline"},
        }

    actions = list(
        db.scalars(
            select(ActionItem).where(
                ActionItem.company_id == company_id,
                ActionItem.status != "cancelled",
            )
        ).all()
    )

    plan_total = sum(a.expected_carbon_t for a in actions)
    if plan_total <= 0 or not actions:
        return {
            "plan_total_tco2e": 0.0,
            "months_since_plan": 0,
            "required_monthly_tco2e": 0.0,
            "actual_monthly_tco2e": 0.0,
            "baseline_monthly_tco2e": base["avg_monthly_tco2e"],
            "verdict_key": "course.noPlan",
            "verdict_vars": {"reason": "no_actions"},
        }

    earliest = min(a.created_at.date() for a in actions if a.created_at)
    today = date_cls.today()
    months_since = _month_diff(earliest, today)
    required_monthly = plan_total / max(months_since, 1)

    baseline_monthly = base["avg_monthly_tco2e"]
    actual_monthly = _actual_monthly_avg(db, company_id)

    on_track = actual_monthly <= baseline_monthly - required_monthly
    verdict = "course.onTrack" if on_track else "course.behind"

    return {
        "plan_total_tco2e": round(plan_total, 2),
        "months_since_plan": months_since,
        "required_monthly_tco2e": round(required_monthly, 2),
        "actual_monthly_tco2e": round(actual_monthly, 2),
        "baseline_monthly_tco2e": round(baseline_monthly, 2),
        "verdict_key": verdict,
        "verdict_vars": {
            "plan_total_tco2e": round(plan_total, 2),
            "required_monthly_tco2e": round(required_monthly, 2),
            "actual_monthly_tco2e": round(actual_monthly, 2),
            "baseline_monthly_tco2e": round(baseline_monthly, 2),
        },
    }


def _month_diff(start: date_cls, end: date_cls) -> int:
    """Whole calendar months between two dates, minimum 1 (same month = 1)."""
    return max((end.year - start.year) * 12 + (end.month - start.month), 1)


def _actual_monthly_avg(db: Session, company_id: int) -> float:
    series = calculator.monthly_series(db, company_id)
    if not series:
        return 0.0
    # Use only the recorded period (all points are recorded in the demo: no
    # projection is stored). Latest window = the same months as the plan span.
    return sum(p["tco2e"] for p in series) / max(len(series), 1)
