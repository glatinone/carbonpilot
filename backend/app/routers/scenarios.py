"""Scenario endpoints: explicit what-if simulation and constraint search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import scenario as scenario_engine
from app.models import Company, ScenarioRecord
from app.schemas import ConstraintRequest, ScenarioRequest

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _require_company(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")
    return company


@router.post("/run")
def run(
    payload: ScenarioRequest,
    company_id: int = Query(1),
    db: Session = Depends(get_db),
) -> dict:
    _require_company(db, company_id)
    result = scenario_engine.run_scenario(
        db,
        company_id,
        [i.model_dump() for i in payload.interventions],
        label=payload.label,
    )

    if payload.save:
        record = ScenarioRecord(
            company_id=company_id,
            name=result["label"],
            interventions=[i.model_dump() for i in payload.interventions],
            result=result,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        result["scenario_id"] = record.id

    return result


@router.post("/constraints")
def constraints(
    payload: ConstraintRequest,
    company_id: int = Query(1),
    db: Session = Depends(get_db),
) -> dict:
    _require_company(db, company_id)
    return scenario_engine.find_feasible(
        db,
        company_id,
        min_carbon_reduction_pct=payload.min_carbon_reduction_pct,
        max_cost_increase_usd=payload.max_cost_increase_usd,
        max_interventions=payload.max_interventions,
        limit=payload.limit,
    )


@router.get("")
def list_saved(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    _require_company(db, company_id)
    rows = db.scalars(
        select(ScenarioRecord)
        .where(ScenarioRecord.company_id == company_id)
        .order_by(ScenarioRecord.id.desc())
        .limit(20)
    ).all()
    return {
        "count": len(rows),
        "scenarios": [
            {"id": r.id, "name": r.name, "interventions": r.interventions, "result": r.result}
            for r in rows
        ],
    }


@router.delete("/{scenario_id}")
def delete_saved(scenario_id: int, company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    record = db.get(ScenarioRecord, scenario_id)
    if record is None or record.company_id != company_id:
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.delete(record)
    db.commit()
    return {"deleted": scenario_id}
