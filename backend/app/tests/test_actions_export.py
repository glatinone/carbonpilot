"""Action-plan export contract tests.

The export is the artifact the demo hands over, so it is asserted as a contract
between the stored actions and the document: every tracked action appears, and
the stated totals equal the sum of those actions. Nothing here freezes wording.

The API is exercised through the real router with the database dependency
overridden onto an in-memory SQLite session, so the assertions run against the
production code path rather than a reimplementation of the formatting.
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import ActionItem, Company


def _add_actions(session: Session, company_id: int, rows: list[tuple[str, str, float, float]]) -> None:
    for owner, task, carbon, cost in rows:
        session.add(
            ActionItem(
                company_id=company_id,
                owner=owner,
                task=task,
                expected_carbon_t=carbon,
                expected_cost_usd=cost,
                status="open",
            )
        )
    session.commit()


@pytest.fixture()
def api():
    """A TestClient wired to a throwaway in-memory database.

    TestClient is deliberately not used as a context manager: entering it runs
    the app lifespan, which would seed the developer's demo database.
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

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), session, company.id
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_empty_plan_export_states_there_is_nothing_to_do(api) -> None:
    client, _, company_id = api

    markdown = client.get(f"/api/actions/export?company_id={company_id}")
    assert markdown.status_code == 200
    assert "No actions tracked yet" in markdown.text

    sheet = client.get(f"/api/actions/export?fmt=csv&company_id={company_id}")
    assert sheet.status_code == 200
    assert len(list(csv.reader(io.StringIO(sheet.text)))) == 1  # header only


def test_csv_export_totals_are_the_sum_of_the_tracked_actions(api) -> None:
    client, session, company_id = api
    _add_actions(
        session,
        company_id,
        [
            ("Engineering", "Right-size weekend cloud workloads", -57.5, -3_000_000.0),
            ("Facilities", "Office energy efficiency retrofit", -459.7, -74_249.75),
        ],
    )

    response = client.get(f"/api/actions/export?fmt=csv&company_id={company_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = list(csv.reader(io.StringIO(response.text)))
    header, *body = rows
    assert len(body) == 2
    assert {row[1] for row in body} == {
        "Right-size weekend cloud workloads",
        "Office energy efficiency retrofit",
    }
    # The contract: the numbers in the sheet are the stored expectations, summed.
    assert sum(float(row[2]) for row in body) == pytest.approx(-517.2)
    assert sum(float(row[3]) for row in body) == pytest.approx(-3_074_249.75)
    assert [h for h in header if "carbon" in h.lower()]


def test_markdown_export_carries_every_action_and_its_owner(api) -> None:
    client, session, company_id = api
    _add_actions(
        session,
        company_id,
        [("Engineering", "Optimise weekend workloads", -57.5, -3_000_000.0)],
    )

    response = client.get(f"/api/actions/export?company_id={company_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]

    assert "Optimise weekend workloads" in response.text
    assert "Engineering" in response.text
    assert "Test Co" in response.text


def test_export_filename_follows_the_company_and_format(api) -> None:
    client, _, company_id = api

    markdown = client.get(f"/api/actions/export?company_id={company_id}")
    assert "carbonpilot-actions-test-co.md" in markdown.headers["content-disposition"]

    sheet = client.get(f"/api/actions/export?fmt=csv&company_id={company_id}")
    assert "carbonpilot-actions-test-co.csv" in sheet.headers["content-disposition"]


def test_unknown_company_export_is_404(api) -> None:
    client, _, _ = api
    assert client.get("/api/actions/export?company_id=999").status_code == 404


def test_unsupported_format_is_rejected(api) -> None:
    client, _, company_id = api
    assert client.get(f"/api/actions/export?fmt=pdf&company_id={company_id}").status_code == 422


def test_csv_stays_machine_readable_while_markdown_is_rendered(api) -> None:
    """The two formats exist for different readers, so the difference is a contract."""
    client, session, company_id = api
    _add_actions(session, company_id, [("Finance", "Fleet electrification", -459.7, -3_000_000.0)])

    sheet = list(
        csv.reader(io.StringIO(client.get(f"/api/actions/export?fmt=csv&company_id={company_id}").text))
    )
    _, *rows = sheet
    csv_cost = rows[0][3]
    # A spreadsheet has to read this as a number, not as text.
    assert float(csv_cost) == pytest.approx(-3_000_000.0)
    assert "," not in csv_cost

    markdown = client.get(f"/api/actions/export?company_id={company_id}").text
    # The same value, grouped for a person reading the document.
    assert "-3,000,000.00" in markdown
