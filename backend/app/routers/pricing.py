"""Carbon pricing scenario endpoints.

One human number goes in (USD per tonne CO2e); the deterministic engine does the
rest. This is the same audit trail as everywhere else: no LLM arithmetic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import pricing as pricing_engine
from app.models import Company

router = APIRouter(prefix="/api", tags=["pricing"])


class PricingRequest(BaseModel):
    company_id: int = Field(1, ge=1)
    price_usd_per_t: float = Field(50.0, ge=0.0, le=10000.0)


@router.post("/pricing/scenario")
def pricing_scenario(
    payload: PricingRequest, db: Session = Depends(get_db)
) -> dict:
    company = db.get(Company, payload.company_id)
    if company is None:
        raise HTTPException(
            status_code=404, detail=f"Company {payload.company_id} not found"
        )
    result = pricing_engine.price_scenario(
        db, payload.company_id, payload.price_usd_per_t
    )
    result["company"] = {"id": company.id, "name": company.name, "region": company.region}
    return result
