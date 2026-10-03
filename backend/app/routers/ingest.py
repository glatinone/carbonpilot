"""CSV ingestion: semantic column mapping, then deterministic calculation.

Handles both shapes a real company actually sends:
  * long  — date, category, activity, value, unit, cost
  * wide  — date, electricity_kwh, cloud_compute, flight_km, ... (one column per stream)
"""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine.calculator import ingest_rows, recalculate
from app.engine.mapping import infer_activity_type, map_columns
from app.models import Activity, Company

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

DATE_HEADERS = {"date", "month", "period", "tanggal", "billing_period"}
VALUE_HEADERS = {"value", "amount", "usage", "quantity", "consumption", "total", "jumlah"}
COST_HEADERS = {"cost", "spend", "price", "amount_usd", "biaya", "total_cost"}
UNIT_HEADERS = {"unit", "uom", "satuan"}
NAME_HEADERS = {"activity", "activity_type", "item", "metric", "type", "category", "kategori", "jenis"}
IGNORE_HEADERS = {"notes", "note", "comment", "remarks", "description", "id", "source"}


def _norm(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(text).strip().lower()).strip("_")


def _parse_csv(text: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")
    headers = [h.strip() for h in reader.fieldnames if h]
    rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in reader]
    return headers, [r for r in rows if any(r.values())]


def _detect_shape(headers: list[str]) -> str:
    """'long' when there is a name column plus a value column, else 'wide'."""
    normalized = {_norm(h) for h in headers}
    has_name = bool(normalized & NAME_HEADERS)
    has_value = bool(normalized & VALUE_HEADERS)
    return "long" if (has_name and has_value) else "wide"


def _pick(headers: list[str], candidates: set[str]) -> str | None:
    for header in headers:
        if _norm(header) in candidates:
            return header
    return None


def _preview(text: str, filename: str) -> dict:
    headers, rows = _parse_csv(text)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")

    shape = _detect_shape(headers)
    unit_col = _pick(headers, UNIT_HEADERS)
    suggested: list[dict] = []
    ambiguous: list[str] = []

    if shape == "long":
        name_col = _pick(headers, NAME_HEADERS)
        for value in {row.get(name_col, "") for row in rows}:
            if not value:
                continue
            mapped = infer_activity_type(value)
            suggested.append(mapped.to_dict())
            if mapped.confidence < 0.6:
                ambiguous.append(value)
    else:
        for header in headers:
            if _norm(header) in DATE_HEADERS | COST_HEADERS | UNIT_HEADERS | IGNORE_HEADERS:
                continue
            unit_sample = rows[0].get(unit_col, "") if unit_col else ""
            mapped = infer_activity_type(header, unit_sample)
            suggested.append(mapped.to_dict())
            if mapped.confidence < 0.6:
                ambiguous.append(header)

    return {
        "filename": filename,
        "shape": shape,
        "columns": headers,
        "suggested": suggested,
        "sample_rows": rows[:5],
        "ambiguous": ambiguous,
    }


def _rows_from_long(headers: list[str], rows: list[dict], column_map: dict[str, str]) -> list[dict]:
    date_col = _pick(headers, DATE_HEADERS)
    value_col = _pick(headers, VALUE_HEADERS)
    name_col = _pick(headers, NAME_HEADERS)
    cost_col = _pick(headers, COST_HEADERS)
    unit_col = _pick(headers, UNIT_HEADERS)

    if date_col is None:
        raise HTTPException(status_code=400, detail="Long-format CSV needs a date/month column")
    if value_col is None:
        raise HTTPException(status_code=400, detail="Long-format CSV needs a value/usage column")
    if name_col is None:
        raise HTTPException(status_code=400, detail="Long-format CSV needs an activity column")

    out: list[dict] = []
    for row in rows:
        raw_name = row.get(name_col, "")
        mapped = infer_activity_type(raw_name, row.get(unit_col, "") if unit_col else None)
        activity_type = column_map.get(raw_name, mapped.activity_type)
        out.append(
            {
                "date": row.get(date_col),
                "category": mapped.category,
                "activity_type": activity_type,
                "value": row.get(value_col),
                "unit": (row.get(unit_col) if unit_col else None) or mapped.unit,
                "cost": row.get(cost_col) if cost_col else 0.0,
                "source": "csv:long",
                "meta": {"month": str(row.get(date_col, ""))[:7]},
            }
        )
    return out


def _rows_from_wide(headers: list[str], rows: list[dict], column_map: dict[str, str]) -> list[dict]:
    date_col = _pick(headers, DATE_HEADERS)
    cost_col = _pick(headers, COST_HEADERS)
    unit_col = _pick(headers, UNIT_HEADERS)
    if date_col is None:
        raise HTTPException(status_code=400, detail="Wide-format CSV needs a date/month column")

    value_headers = [
        h
        for h in headers
        if _norm(h) not in DATE_HEADERS | COST_HEADERS | UNIT_HEADERS | IGNORE_HEADERS
    ]

    out: list[dict] = []
    for row in rows:
        for header in value_headers:
            cell = row.get(header)
            if cell in (None, ""):
                continue
            mapped = infer_activity_type(header, row.get(unit_col) if unit_col else None)
            activity_type = column_map.get(header, mapped.activity_type)
            out.append(
                {
                    "date": row.get(date_col),
                    "category": mapped.category,
                    "activity_type": activity_type,
                    "value": cell,
                    "unit": mapped.unit,
                    "cost": 0.0,
                    "source": "csv:wide",
                    "meta": {"month": str(row.get(date_col, ""))[:7]},
                }
            )
    return out


@router.post("/preview")
async def preview(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return _preview(text, file.filename or "upload.csv")


@router.post("")
async def ingest(
    file: UploadFile = File(...),
    company_id: int = Form(1),
    column_map: str = Form("{}"),
    db: Session = Depends(get_db),
) -> dict:
    if db.get(Company, company_id) is None:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    headers, rows = _parse_csv(text)
    try:
        overrides: dict[str, str] = json.loads(column_map or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="column_map must be a JSON object") from None

    shape = _detect_shape(headers)
    mapped_rows = (
        _rows_from_long(headers, rows, overrides)
        if shape == "long"
        else _rows_from_wide(headers, rows, overrides)
    )

    result = ingest_rows(db, company_id, mapped_rows)
    recalculate(db, company_id)

    mapping = map_columns(headers)
    return {
        "shape": shape,
        "activities_created": result["activities_created"],
        "rows_skipped": result["rows_skipped"],
        "skipped": result["skipped"],
        "mapping": mapping,
    }


@router.post("/demo")
def load_demo(company_id: int = 1, db: Session = Depends(get_db)) -> dict:
    """Re-seed the synthetic 12-month dataset (used by the demo 'Reset' button)."""
    from app.seed import seed_demo

    return seed_demo(db)


@router.get("/activities")
def activities(
    company_id: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    from sqlalchemy import select

    rows = db.scalars(
        select(Activity)
        .where(Activity.company_id == company_id)
        .order_by(Activity.date.desc())
        .limit(limit)
    ).all()
    return {
        "count": len(rows),
        "activities": [
            {
                "id": a.id,
                "date": a.date.isoformat(),
                "category": a.category,
                "activity_type": a.activity_type,
                "value": a.value,
                "unit": a.unit,
                "cost": a.cost,
                "source": a.source,
            }
            for a in rows
        ],
    }
