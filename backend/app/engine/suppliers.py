"""Supplier segment attribution — where procurement carbon sits.

The demo dataset records procurement as a single spend line (activity_type
'procurement_usd'), so there is no supplier field in the source data. To make
the spend visible at the level a buyer actually decides, the engine splits the
procurement spend and its embedded emissions across a FIXED, documented set of
segments. This is demo attribution, not inventory data — the shares are a
stated assumption, never a measured counterparty split. The UI must say so.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.engine import calculator

# Demo attribution shares. Sums to 1.0 by construction.
SUPPLIER_SEGMENTS: list[dict] = [
    {"name": "IT Infrastructure", "share": 0.30},
    {"name": "Cloud & SaaS", "share": 0.25},
    {"name": "Facilities & Utilities", "share": 0.20},
    {"name": "Logistics & Transport", "share": 0.15},
    {"name": "Professional Services", "share": 0.10},
]

ATTRIBUTION_NOTE = (
    "Demo attribution: procurement is recorded as a single spend line, so these "
    "segments split it by fixed, documented shares. They are not measured "
    "counterparty emissions."
)


def supplier_breakdown(db: Session, company_id: int) -> dict:
    """Split procurement spend and embedded carbon across the fixed segments."""
    breakdown = calculator.breakdown(db, company_id, by="activity_type")
    procurement_row = next(
        (row for row in breakdown if row["key"] == "procurement_usd"), None
    )
    if procurement_row is None:
        return {
            "procurement_spend_usd": 0.0,
            "procurement_tco2e": 0.0,
            "segments": [],
            "attribution_note": ATTRIBUTION_NOTE,
            "incomplete": True,
        }

    spend = procurement_row["cost_usd"]
    tco2e = procurement_row["tco2e"]
    segments = [
        {
            "name": segment["name"],
            "share_pct": round(segment["share"] * 100, 1),
            "spend_usd": round(spend * segment["share"], 2),
            "embedded_tco2e": round(tco2e * segment["share"], 2),
        }
        for segment in SUPPLIER_SEGMENTS
    ]
    return {
        "procurement_spend_usd": round(spend, 2),
        "procurement_tco2e": round(tco2e, 2),
        "segments": segments,
        "attribution_note": ATTRIBUTION_NOTE,
        "incomplete": False,
    }
