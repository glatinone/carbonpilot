"""Target-trajectory contracts — the stated % target drawn linearly over years.

The projection is a straight line from today's footprint to the target at the
target year. The property tests here are about that shape: the midpoint must be
exactly halfway, the target year must land exactly on the target, and the
endpoint must validate its inputs like every other engine endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.engine import trajectory
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

def test_projection_is_linear_from_baseline_to_target(db: Session) -> None:
    base = trajectory.project_trajectory(db, 1, 42.0, 2030, price_usd_per_t=50.0)
    baseline = base["baseline_total_tco2e"]
    target = base["target_total_tco2e"]

    first, last = base["years"][0], base["years"][-1]
    assert first["projected_tco2e"] == pytest.approx(baseline, rel=1e-6)
    assert last["projected_tco2e"] == pytest.approx(target, rel=1e-6)

    # Midpoint of the year range must be exactly halfway.
    years = [y["year"] for y in base["years"]]
    mid_index = len(years) // 2
    if len(years) % 2 == 0:
        # two centre years straddle the exact halfway point
        around = base["years"][mid_index - 1 : mid_index + 1]
        avg = sum(y["projected_tco2e"] for y in around) / 2
        assert avg == pytest.approx((baseline + target) / 2, rel=1e-6)
    else:
        assert base["years"][mid_index]["projected_tco2e"] == pytest.approx(
            (baseline + target) / 2, rel=1e-6
        )


def test_carbon_cost_is_projected_times_price(db: Session) -> None:
    base = trajectory.project_trajectory(db, 1, 42.0, 2030, price_usd_per_t=100.0)
    for year in base["years"]:
        assert year["carbon_cost_usd"] == pytest.approx(
            year["projected_tco2e"] * 100.0, rel=1e-6
        )


def test_incomplete_company_yields_no_years(db: Session) -> None:
    result = trajectory.project_trajectory(db, 2, 42.0, 2030)
    assert result["years"] == []
    assert result["note"] is not None


# --------------------------------------------------------------------------- #
# HTTP contracts
# --------------------------------------------------------------------------- #

def test_trajectory_endpoint_returns_structured_result(api: TestClient) -> None:
    response = api.post(
        "/api/trajectory",
        json={
            "company_id": 1,
            "target_reduction_pct": 50,
            "target_year": 2030,
            "price_usd_per_t": 75,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["name"] == "PT Nusantara Digital"
    assert body["target_reduction_pct"] == 50
    assert body["target_year"] == 2030
    assert body["price_usd_per_t"] == 75
    assert len(body["years"]) >= 1
    assert body["years"][0]["year"] <= body["years"][-1]["year"]


def test_trajectory_rejects_out_of_range_target(api: TestClient) -> None:
    response = api.post(
        "/api/trajectory",
        json={"company_id": 1, "target_reduction_pct": 0, "target_year": 2030},
    )
    assert response.status_code == 422
    response = api.post(
        "/api/trajectory",
        json={"company_id": 1, "target_reduction_pct": 100, "target_year": 2030},
    )
    assert response.status_code == 422


def test_trajectory_rejects_past_target_year(api: TestClient) -> None:
    response = api.post(
        "/api/trajectory",
        json={"company_id": 1, "target_reduction_pct": 42, "target_year": 2020},
    )
    assert response.status_code == 422


def test_trajectory_rejects_unknown_company(api: TestClient) -> None:
    response = api.post(
        "/api/trajectory",
        json={"company_id": 999, "target_reduction_pct": 42, "target_year": 2030},
    )
    assert response.status_code == 404
