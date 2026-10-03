"""Emission factor library.

Loading, seeding and region-aware lookup. Every factor carries its `source`
so a calculation can always be traced back to its citation.
"""

from __future__ import annotations

import json
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.models import EmissionFactor

FACTORS_PATH = DATA_DIR / "emission_factors.json"


@lru_cache
def load_factor_library() -> list[dict]:
    with FACTORS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)["factors"]


def seed_emission_factors(db: Session) -> int:
    """Insert any factor that is not in the DB yet. Idempotent."""
    existing = {
        (row.activity_type, row.region, row.unit)
        for row in db.scalars(select(EmissionFactor)).all()
    }
    added = 0
    for spec in load_factor_library():
        key = (spec["activity_type"], spec["region"], spec["unit"])
        if key in existing:
            continue
        db.add(
            EmissionFactor(
                activity_type=spec["activity_type"],
                label=spec["label"],
                category=spec["category"],
                scope=spec["scope"],
                unit=spec["unit"],
                region=spec["region"],
                kg_co2e=spec["kg_co2e"],
                year=spec["year"],
                source=spec["source"],
                uncertainty_pct=spec.get("uncertainty_pct", 20.0),
            )
        )
        added += 1
    if added:
        db.commit()
    return added


def resolve_factor(db: Session, activity_type: str, region: str = "WORLD") -> EmissionFactor:
    """Pick the best factor for an activity type.

    Preference order: exact region -> region fallback to WORLD. Raises
    LookupError when the activity type is unknown, so callers never silently
    invent a number.
    """
    exact = db.scalar(
        select(EmissionFactor).where(
            EmissionFactor.activity_type == activity_type,
            EmissionFactor.region == region,
        )
    )
    if exact:
        return exact

    world = db.scalar(
        select(EmissionFactor).where(
            EmissionFactor.activity_type == activity_type,
            EmissionFactor.region == "WORLD",
        )
    )
    if world:
        return world

    any_region = db.scalars(
        select(EmissionFactor).where(EmissionFactor.activity_type == activity_type)
    ).first()
    if any_region:
        return any_region

    raise LookupError(f"No emission factor registered for activity_type={activity_type!r}")


def search_factors(db: Session, query: str, limit: int = 8) -> list[EmissionFactor]:
    """Free-text search over the factor library (used by the AI agent)."""
    pattern = f"%{query.strip().lower()}%"
    stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.activity_type.ilike(pattern)
            | EmissionFactor.label.ilike(pattern)
            | EmissionFactor.category.ilike(pattern)
        )
        .limit(limit)
    )
    rows = list(db.scalars(stmt).all())
    if rows:
        return rows
    # Fall back to a token match so "electricity usage" still finds something.
    tokens = [t for t in query.lower().replace("_", " ").split() if len(t) > 3]
    results: list[EmissionFactor] = []
    for token in tokens:
        pat = f"%{token}%"
        results.extend(
            db.scalars(
                select(EmissionFactor)
                .where(
                    EmissionFactor.activity_type.ilike(pat)
                    | EmissionFactor.label.ilike(pat)
                )
                .limit(limit)
            ).all()
        )
    deduped: dict[int, EmissionFactor] = {f.id: f for f in results}
    return list(deduped.values())[:limit]


def factor_to_dict(factor: EmissionFactor) -> dict:
    return {
        "id": factor.id,
        "activity_type": factor.activity_type,
        "label": factor.label,
        "scope": factor.scope,
        "unit": factor.unit,
        "region": factor.region,
        "kg_co2e": factor.kg_co2e,
        "year": factor.year,
        "source": factor.source,
        "uncertainty_pct": factor.uncertainty_pct,
    }
