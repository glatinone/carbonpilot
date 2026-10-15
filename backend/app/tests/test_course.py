"""Course-correct contracts — the plan against recorded emissions.

The verdict must always be one of the three keys, the plan totals add up from
the ActionItem rows, and an empty plan must yield course.noPlan rather than a
fake "on track". Company 2 has no activity rows -> no baseline -> noPlan.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.engine import course
from app.engine.factors import seed_emission_factors
from app.main import app
from app.models import ActionItem, Recommendation
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

def test_no_plan_when_no_actions(db: Session) -> None:
    result = course.course_check(db, 1)
    assert result["verdict_key"] == "course.noPlan"
    assert result["plan_total_tco2e"] == 0.0


def test_with_plan_verdict_is_in_the_allowed_set(db: Session) -> None:
    _add_plan(db, 1)
    result = course.course_check(db, 1)
    assert result["verdict_key"] in {
        "course.noPlan",
        "course.onTrack",
        "course.behind",
    }


def test_with_plan_numbers_are_coherent(db: Session) -> None:
    _add_plan(db, 1)
    result = course.course_check(db, 1)
    assert result["plan_total_tco2e"] > 0
    assert result["months_since_plan"] >= 1
    assert result["required_monthly_tco2e"] > 0
    assert result["actual_monthly_tco2e"] > 0
    assert result["baseline_monthly_tco2e"] > 0
    # The verdict sentence data must match the engine numbers.
    assert result["verdict_vars"]["plan_total_tco2e"] == result["plan_total_tco2e"]
    assert result["verdict_vars"]["required_monthly_tco2e"] == result[
        "required_monthly_tco2e"
    ]


def test_no_plan_company_without_data(db: Session) -> None:
    assert course.course_check(db, 2)["verdict_key"] == "course.noPlan"


def _add_plan(db: Session, company_id: int) -> None:
    """Seed one approved recommendation + action so the plan is non-empty."""
    rec = Recommendation(
        company_id=company_id,
        title="Reduce fleet idling",
        description="test plan",
        category="fleet",
        activity_type="fleet_fuel_l",
        carbon_impact_t=120.0,
        cost_impact_usd=-1000.0,
        effort="low",
        confidence_pct=90.0,
        evidence={},
    )
    db.add(rec)
    db.flush()
    db.add(
        ActionItem(
            company_id=company_id,
            recommendation_id=rec.id,
            owner="Test",
            task="do the thing",
            expected_carbon_t=120.0,
            expected_cost_usd=-1000.0,
            status="open",
        )
    )
    db.commit()


# --------------------------------------------------------------------------- #
# HTTP contracts
# --------------------------------------------------------------------------- #

def test_course_endpoint_returns_structured_result(api: TestClient, db: Session) -> None:
    _add_plan(db, 1)
    response = api.get("/api/course?company_id=1")
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["name"] == "PT Nusantara Digital"
    assert body["verdict_key"] in {"course.noPlan", "course.onTrack", "course.behind"}
    assert "verdict_vars" in body


def test_course_rejects_unknown_company(api: TestClient) -> None:
    assert api.get("/api/course?company_id=999").status_code == 404
