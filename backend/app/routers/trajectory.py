"""Target trajectory endpoints — the cost of a stated commitment."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import trajectory as trajectory_engine
from app.models import Company

router = APIRouter(prefix="/api", tags=["trajectory"])


class TrajectoryRequest(BaseModel):
    company_id: int = Field(1, ge=1)
    target_reduction_pct: float = Field(ge=1.0, le=99.0)
    target_year: int = Field(ge=date.today().year + 1)
    price_usd_per_t: float = Field(50.0, ge=0.0, le=10000.0)


@router.post("/trajectory")
def trajectory(payload: TrajectoryRequest, db: Session = Depends(get_db)) -> dict:
    company = db.get(Company, payload.company_id)
    if company is None:
        raise HTTPException(
            status_code=404, detail=f"Company {payload.company_id} not found"
        )
    result = trajectory_engine.project_trajectory(
        db,
        payload.company_id,
        payload.target_reduction_pct,
        payload.target_year,
        payload.price_usd_per_t,
    )
    result["company"] = {"id": company.id, "name": company.name, "region": company.region}
    return result
