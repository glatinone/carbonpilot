"""Recommendation + action-tracking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import recommender
from app.models import ActionItem, Company, Recommendation
from app.schemas import ActionCreate

router = APIRouter(prefix="/api", tags=["actions"])


def _require_company(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")
    return company


@router.get("/recommendations")
def list_recommendations(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    _require_company(db, company_id)
    recs = recommender.list_all(db, company_id)
    if not recs:
        recs = recommender.generate(db, company_id, replace=True)
    return {"count": len(recs), "recommendations": [recommender.to_dict(r) for r in recs]}


@router.post("/recommendations/generate")
def regenerate(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    _require_company(db, company_id)
    recs = recommender.generate(db, company_id, replace=True)
    return {"count": len(recs), "recommendations": [recommender.to_dict(r) for r in recs]}


@router.post("/actions")
def create_action(
    payload: ActionCreate,
    company_id: int = Query(1),
    db: Session = Depends(get_db),
) -> dict:
    _require_company(db, company_id)

    rec: Recommendation | None = None
    if payload.recommendation_id is not None:
        rec = db.get(Recommendation, payload.recommendation_id)
        if rec is None or rec.company_id != company_id:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        rec.status = "approved"

    action = ActionItem(
        company_id=company_id,
        recommendation_id=rec.id if rec else None,
        owner=payload.owner,
        task=payload.task or (rec.title if rec else "Untitled action"),
        expected_carbon_t=rec.carbon_impact_t if rec else 0.0,
        expected_cost_usd=rec.cost_impact_usd if rec else 0.0,
        status="open",
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    return {
        "id": action.id,
        "owner": action.owner,
        "task": action.task,
        "expected_carbon_t": action.expected_carbon_t,
        "expected_cost_usd": action.expected_cost_usd,
        "status": action.status,
    }


@router.get("/actions")
def list_actions(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    _require_company(db, company_id)
    rows = db.scalars(
        select(ActionItem)
        .where(ActionItem.company_id == company_id)
        .order_by(ActionItem.id.desc())
    ).all()

    total_carbon = sum(r.expected_carbon_t for r in rows)
    total_cost = sum(r.expected_cost_usd for r in rows)

    return {
        "count": len(rows),
        "totals": {
            "expected_carbon_t": round(total_carbon, 2),
            "expected_cost_usd": round(total_cost, 2),
        },
        # Overlapping actions would double-count; the plan view sums a chosen set.
        "note": "Totals assume every open action is executed; individual actions may overlap.",
        "actions": [
            {
                "id": r.id,
                "owner": r.owner,
                "task": r.task,
                "expected_carbon_t": r.expected_carbon_t,
                "expected_cost_usd": r.expected_cost_usd,
                "status": r.status,
            }
            for r in rows
        ],
    }


@router.patch("/actions/{action_id}")
def update_action(
    action_id: int,
    status: str = Query(..., pattern="^(open|in_progress|done|cancelled)$"),
    company_id: int = Query(1),
    db: Session = Depends(get_db),
) -> dict:
    action = db.get(ActionItem, action_id)
    if action is None or action.company_id != company_id:
        raise HTTPException(status_code=404, detail="Action not found")
    action.status = status
    db.commit()
    return {"id": action.id, "status": action.status}
