"""Course-correct endpoints — plan vs recorded reality."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import course as course_engine
from app.models import Company

router = APIRouter(prefix="/api", tags=["course"])


@router.get("/course")
def course(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=404, detail=f"Company {company_id} not found"
        )
    result = course_engine.course_check(db, company_id)
    result["company"] = {"id": company.id, "name": company.name, "region": company.region}
    return result
