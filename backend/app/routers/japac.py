"""JAPAC grid-intensity benchmark endpoint.

The route is registered by the application with a ``/api`` prefix, so it lives
at ``/api/japac``; the path here stays bare (``/japac``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine.japac import (
    build_benchmark,
    home_iso3_for_region,
    load_benchmarks,
    measured_electricity,
)
from app.models import Company

router = APIRouter(tags=["japac"])


@router.get("/japac")
def japac_benchmark(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    """Compare the company's measured electricity against JAPAC grid intensities."""
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

    benchmarks = load_benchmarks()
    available = {c["iso3"] for c in benchmarks.get("countries", [])}
    home_iso3 = home_iso3_for_region(company.region, available)
    electricity_kwh, measured_tco2e = measured_electricity(db, company_id)

    return build_benchmark(benchmarks, home_iso3, electricity_kwh, measured_tco2e)
