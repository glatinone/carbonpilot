"""Supplier-attribution contracts — the fixed demo split stays coherent.

Because the source data has no supplier dimension, the engine splits the single
procurement spend line by fixed documented shares. The contracts below pin the
invariants of that split: shares sum to exactly 1, the split reconstructs the
total, the split never changes between calls (it is a constant, not a random
draw), and the attribution note travels with the payload.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.engine import suppliers
from app.engine.factors import seed_emission_factors
from app.main import app
from app.seed import seed_demo


@pytest.fixture(scope="module")
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    seed_emission_factors(session)
    seed_demo(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api(db: Session):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Engine contracts
# --------------------------------------------------------------------------- #

def test_shares_sum_to_one() -> None:
    assert sum(s["share"] for s in suppliers.SUPPLIER_SEGMENTS) == pytest.approx(1.0)


def test_segments_reconstruct_total(db: Session) -> None:
    result = suppliers.supplier_breakdown(db, 1)
    assert result["incomplete"] is False
    assert result["procurement_spend_usd"] > 0
    assert result["procurement_tco2e"] > 0

    sum_spend = sum(s["spend_usd"] for s in result["segments"])
    sum_tco2e = sum(s["embedded_tco2e"] for s in result["segments"])
    # Allow the residual of rounding both sides to 2dp at different points.
    assert sum_spend == pytest.approx(result["procurement_spend_usd"], abs=0.02)
    assert sum_tco2e == pytest.approx(result["procurement_tco2e"], abs=0.02)


def test_attribution_is_deterministic(db: Session) -> None:
    first = suppliers.supplier_breakdown(db, 1)
    second = suppliers.supplier_breakdown(db, 1)
    assert first["segments"] == second["segments"]
    assert first["attribution_note"] == second["attribution_note"]
    assert "demo" in first["attribution_note"].lower() or "attribution" in first[
        "attribution_note"
    ].lower()


def test_incomplete_when_no_procurement_line(db: Session) -> None:
    result = suppliers.supplier_breakdown(db, 2)
    assert result["incomplete"] is True
    assert result["segments"] == []


# --------------------------------------------------------------------------- #
# HTTP contracts
# --------------------------------------------------------------------------- #

def test_suppliers_endpoint_returns_structured_result(api: TestClient) -> None:
    response = api.get("/api/suppliers?company_id=1")
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["name"] == "PT Nusantara Digital"
    assert body["procurement_spend_usd"] > 0
    assert len(body["segments"]) == len(suppliers.SUPPLIER_SEGMENTS)
    assert body["attribution_note"]


def test_suppliers_rejects_unknown_company(api: TestClient) -> None:
    assert api.get("/api/suppliers?company_id=999").status_code == 404
