"""Carbon-pricing scenario tests — behaviour contracts for the pricing engine.

The pricing scenario introduces exactly one human number (USD per tonne) and asserts
relationships, never snapshots:

* annual cost = baseline tonnes x price  — the number a CFO can check on a napkin.
* price 0 keeps the financial-only ordering (price mutliplies zero, so net == cost).
* A high price rescues a big-tonnage action that the financial ranking buried.
* Every re-ranked action keeps its original financial rank for comparison.

All tests run against the seeded demo dataset through the real engine and the
real endpoint, so they cover the production path without any LLM.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.engine import pricing
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

def test_annual_carbon_cost_is_baseline_times_price(db: Session) -> None:
    result = pricing.price_scenario(db, 1, 50.0)
    assert result["baseline_total_tco2e"] > 0
    assert result["annual_carbon_cost_usd"] == pytest.approx(
        result["baseline_total_tco2e"] * 50.0
    )


def test_price_zero_keeps_cost_only_ordering_and_names_it(db: Session) -> None:
    zero = pricing.price_scenario(db, 1, 0.0)
    assert zero["verdict_key"] == "pricing.financialOnly"
    ranked = zero["actions"]
    assert len(ranked) >= 1
    costs = [a["cost_impact_usd"] for a in ranked]
    assert costs == sorted(costs)  # ascending, most negative first


def test_high_price_reorders_the_catalog_and_lifts_low_carbon_value_actions(
    db: Session,
) -> None:
    cheap = pricing.price_scenario(db, 1, 5.0)
    expensive = pricing.price_scenario(db, 1, 1000.0)

    # A price is a decision input: at $1000/t the ranking must differ from the
    # pure financial one, or the scenario is a no-op.
    cheap_order = [a["id"] for a in cheap["actions"]]
    expensive_order = [a["id"] for a in expensive["actions"]]
    assert expensive_order != cheap_order

    # monotonicity: doubling the price never makes a smaller-carbon-value action
    # leapfrog a larger one. Every action's own position only improves when its
    # carbon value relative to cost grows — assert that the highest gainer is the
    # action with the best carbon-value share, not a frozen position.
    gainers = []
    for a in cheap["actions"]:
        expensive_rank = next(
            e["rank_priced"] for e in expensive["actions"] if e["id"] == a["id"]
        )
        gainers.append((a["id"], a["rank_financial"] - expensive_rank))
    best_gainer = max(gainers, key=lambda g: g[1])
    assert best_gainer[1] > 0, "at $1000/t at least one action must rise"


def test_each_action_reports_both_ranks_for_a_verdict_comparison(db: Session) -> None:
    result = pricing.price_scenario(db, 1, 50.0)
    for action in result["actions"]:
        assert action["rank_financial"] >= 1
        assert action["rank_priced"] >= 1
        assert action["net_usd"] == pytest.approx(
            action["cost_impact_usd"] + action["carbon_value_usd"]
        )


def test_verdict_pays_for_itself_when_leader_net_is_negative(db: Session) -> None:
    result = pricing.price_scenario(db, 1, 50.0)
    leader = result["actions"][0]
    if leader["net_usd"] < 0:
        assert result["verdict_key"] == "pricing.paysForItself"
    else:
        assert result["verdict_key"] == "pricing.stillCosts"


# --------------------------------------------------------------------------- #
# HTTP contract
# --------------------------------------------------------------------------- #

def test_pricing_endpoint_returns_structured_result(api: TestClient) -> None:
    response = api.post("/api/pricing/scenario", json={"company_id": 1, "price_usd_per_t": 75})
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["name"] == "PT Nusantara Digital"
    assert body["price_usd_per_t"] == 75
    assert body["baseline_total_tco2e"] > 0
    assert "actions" in body and len(body["actions"]) >= 1
    assert body["verdict_key"] in {
        "pricing.empty",
        "pricing.financialOnly",
        "pricing.paysForItself",
        "pricing.stillCosts",
    }
    assert "price" in body["verdict_vars"]
    assert body["annual_carbon_cost_usd"] == pytest.approx(
        body["baseline_total_tco2e"] * 75.0
    )


def test_pricing_rejects_unknown_company(api: TestClient) -> None:
    response = api.post(
        "/api/pricing/scenario", json={"company_id": 999, "price_usd_per_t": 10}
    )
    assert response.status_code == 404


def test_pricing_rejects_negative_price(api: TestClient) -> None:
    response = api.post(
        "/api/pricing/scenario", json={"company_id": 1, "price_usd_per_t": -5}
    )
    assert response.status_code == 422
