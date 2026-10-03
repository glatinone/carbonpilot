"""Action-approval contract tests.

Approving a recommendation turns it into a tracked, owner-assigned action, and
the plan's totals sum every tracked action. Approval must therefore be
idempotent: a second click that produced a second row would silently
double-count that action's expected impact in the numbers shown to a CFO.

Exercised through the real router with the database dependency overridden onto
an in-memory session, so the assertions cover the production path.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import ActionItem, Company, Recommendation


@pytest.fixture()
def api():
    """TestClient, session, company id and recommendation id.

    Not used as a context manager: entering it runs the app lifespan, which
    would seed the developer's demo database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    company = Company(name="Test Co", region="ID")
    session.add(company)
    session.commit()
    session.refresh(company)

    recommendation = Recommendation(
        company_id=company.id,
        title="Office energy efficiency retrofit",
        description="Apply a 15% reduction to purchased electricity.",
        category="electricity",
        activity_type="electricity_kwh",
        carbon_impact_t=459.7,
        cost_impact_usd=-74249.75,
        effort="low",
        confidence_pct=90.4,
    )
    session.add(recommendation)
    session.commit()
    session.refresh(recommendation)

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), session, company.id, recommendation.id
    finally:
        app.dependency_overrides.clear()
        session.close()


def _stored_actions(session: Session) -> list[ActionItem]:
    return list(session.scalars(select(ActionItem)).all())


def test_approving_the_same_recommendation_twice_tracks_one_action(api) -> None:
    client, session, company_id, rec_id = api

    first = client.post(
        f"/api/actions?company_id={company_id}",
        json={"recommendation_id": rec_id, "owner": "Engineering"},
    )
    second = client.post(
        f"/api/actions?company_id={company_id}",
        json={"recommendation_id": rec_id, "owner": "Engineering"},
    )

    assert first.status_code == 200 and second.status_code == 200
    # The caller gets the same action back, so a double submit looks idempotent
    # to the UI as well as to the database.
    assert first.json()["id"] == second.json()["id"]
    assert len(_stored_actions(session)) == 1


def test_duplicate_approval_does_not_double_count_the_plan_totals(api) -> None:
    client, _, company_id, rec_id = api

    for _ in range(3):
        client.post(
            f"/api/actions?company_id={company_id}",
            json={"recommendation_id": rec_id, "owner": "Engineering"},
        )

    listing = client.get(f"/api/actions?company_id={company_id}").json()
    assert listing["count"] == 1
    assert listing["totals"]["expected_carbon_t"] == pytest.approx(459.7)
    assert listing["totals"]["expected_cost_usd"] == pytest.approx(-74249.75)


def test_approval_marks_the_recommendation_approved(api) -> None:
    client, session, company_id, rec_id = api

    client.post(
        f"/api/actions?company_id={company_id}",
        json={"recommendation_id": rec_id, "owner": "Engineering"},
    )

    session.expire_all()
    assert session.get(Recommendation, rec_id).status == "approved"


def test_manual_actions_are_not_deduplicated(api) -> None:
    """Only approvals carry a dedupe key; two separate ad-hoc tasks stay separate."""
    client, session, company_id, _ = api

    for _ in range(2):
        response = client.post(
            f"/api/actions?company_id={company_id}",
            json={"owner": "Facilities", "task": "Investigate the water bill"},
        )
        assert response.status_code == 200

    assert len(_stored_actions(session)) == 2


def test_unknown_recommendation_is_rejected_without_writing(api) -> None:
    client, session, company_id, _ = api

    response = client.post(
        f"/api/actions?company_id={company_id}",
        json={"recommendation_id": 999, "owner": "Engineering"},
    )

    assert response.status_code == 404
    assert _stored_actions(session) == []
