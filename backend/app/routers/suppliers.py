"""Supplier segment attribution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import suppliers as suppliers_engine
from app.models import Company

router = APIRouter(prefix="/api", tags=["suppliers"])


@router.get("/suppliers")
def suppliers(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=404, detail=f"Company {company_id} not found"
        )
    result = suppliers_engine.supplier_breakdown(db, company_id)
    result["company"] = {"id": company.id, "name": company.name, "region": company.region}
    return result
