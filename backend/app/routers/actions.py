"""Recommendation + action-tracking endpoints."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
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


def _action_dict(row: ActionItem) -> dict:
    """The wire shape for one action — shared by create and list."""
    return {
        "id": row.id,
        "owner": row.owner,
        "task": row.task,
        "expected_carbon_t": row.expected_carbon_t,
        "expected_cost_usd": row.expected_cost_usd,
        "status": row.status,
    }


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

        # Approving is idempotent. A second click (or a double-submit) must not
        # create a second action for the same recommendation — the plan's totals
        # sum every tracked action, so a duplicate silently double-counts its
        # impact.
        existing = db.scalar(
            select(ActionItem).where(
                ActionItem.company_id == company_id,
                ActionItem.recommendation_id == rec.id,
            )
        )
        if existing is not None:
            db.commit()  # persist the approval itself
            db.refresh(existing)
            return _action_dict(existing)

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

    return _action_dict(action)


def _action_rows(db: Session, company_id: int) -> list[ActionItem]:
    """Tracked actions, newest first — the one query behind both list and export."""
    return list(
        db.scalars(
            select(ActionItem)
            .where(ActionItem.company_id == company_id)
            .order_by(ActionItem.id.desc())
        ).all()
    )


@router.get("/actions")
def list_actions(company_id: int = Query(1), db: Session = Depends(get_db)) -> dict:
    _require_company(db, company_id)
    rows = _action_rows(db, company_id)

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
        "actions": [_action_dict(r) for r in rows],
    }


_EXPORT_HEADERS = [
    "Owner",
    "Action",
    "Carbon saving (tCO2e/yr)",
    "Cost impact (USD/yr)",
    "Status",
]


def _export_rows(rows: list[ActionItem], *, formatted: bool) -> list[list[str]]:
    """One place that decides what a row says.

    ``formatted`` adds thousands separators for the human-readable document. The
    CSV keeps raw numbers so a spreadsheet reads them as numbers rather than
    text.
    """

    def number(value: float) -> str:
        return f"{value:,.2f}" if formatted else f"{value:.2f}"

    return [
        [
            row.owner or "Unassigned",
            row.task,
            number(row.expected_carbon_t),
            number(row.expected_cost_usd),
            row.status,
        ]
        for row in rows
    ]


def _as_csv(rows: list[ActionItem]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_EXPORT_HEADERS)
    writer.writerows(_export_rows(rows, formatted=False))
    return buffer.getvalue()


def _as_markdown(
    company: Company,
    rows: list[ActionItem],
    total_carbon: float,
    total_cost: float,
    generated: str,
) -> str:
    def cell(value: str) -> str:
        # A pipe inside a task title would break the table's column count.
        return value.replace("|", r"\|")

    lines = [
        f"# CarbonPilot action plan — {company.name}",
        "",
        f"Generated {generated} · grid region {company.region}",
        "",
        f"{len(rows)} tracked action(s). If every action is executed the expected saving is "
        f"{total_carbon:,.1f} tCO2e/year, with a net cost impact of {total_cost:+,.0f} USD/year.",
        "",
        "| " + " | ".join(_EXPORT_HEADERS) + " |",
        "|" + "---|" * len(_EXPORT_HEADERS),
    ]
    table = _export_rows(rows, formatted=True)
    if table:
        for cells in table:
            lines.append("| " + " | ".join(cell(c) for c in cells) + " |")
    else:
        lines.append("| — | No actions tracked yet | — | — | — |")

    lines += [
        "",
        "Carbon saving is the expected annual reduction. For cost, a negative figure is a saving "
        "and a positive one is a net investment.",
        "",
        "## How these numbers are produced",
        "",
        "Every figure is activity data multiplied by a cited emission factor, computed by the "
        "deterministic engine. The language model chooses which analysis to run and explains the "
        "result; it never produces a carbon number.",
        "",
        "Expected impact is annualised from the recorded activity history and assumes reductions "
        "apply uniformly with emission factors held constant — no rebound effect and no learning "
        "curve are modelled. Totals assume every listed action is executed, so the true combined "
        "saving can be smaller than the sum where actions overlap.",
    ]
    return "\n".join(lines) + "\n"


@router.get("/actions/export")
def export_actions(
    fmt: str = Query("md", pattern="^(md|csv)$"),
    company_id: int = Query(1),
    db: Session = Depends(get_db),
) -> Response:
    """Download the tracked action plan as a document you can send to someone.

    The demo ends on a plan an operations manager has to justify to their CFO.
    A file they can attach to that conversation is the difference between a
    dashboard and a deliverable.
    """
    company = _require_company(db, company_id)
    rows = _action_rows(db, company_id)
    total_carbon = sum(row.expected_carbon_t for row in rows)
    total_cost = sum(row.expected_cost_usd for row in rows)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    slug = "".join(ch if ch.isalnum() else "-" for ch in company.name.lower()).strip("-")

    if fmt == "csv":
        body, media_type, extension = _as_csv(rows), "text/csv", "csv"
    else:
        body = _as_markdown(company, rows, total_carbon, total_cost, generated)
        media_type, extension = "text/markdown", "md"

    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="carbonpilot-actions-{slug}.{extension}"'
        },
    )


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
