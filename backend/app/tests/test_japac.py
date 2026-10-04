"""JAPAC benchmark contract tests.

Two layers:

* :func:`build_benchmark` is pure, so the ordering / rank / delta / arithmetic
  rules are asserted directly against the shipped benchmark document;
* the HTTP route is exercised through a TestClient with the database dependency
  overridden onto an in-memory session, so the assertions cover the real router
  and the real calculation engine (no network, no demo database).

The router is mounted with the same ``/api`` prefix the application uses, so
the test would catch the path drifting away from bare ``/japac``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.engine.calculator import ingest_rows
from app.engine.factors import resolve_factor, seed_emission_factors
from app.engine.japac import build_benchmark, load_benchmarks
from app.models import Company
from app.routers import japac as japac_router

COUNTRY_KEYS = {
    "iso3",
    "country",
    "intensity",
    "year",
    "rank",
    "shares_pct",
    "delta_pct_vs_home",
    "counterfactual_tco2e",
    "counterfactual_delta_tco2e",
}
TOP_LEVEL_KEYS = {
    "basis",
    "unit",
    "source",
    "retrieved_via",
    "licence",
    "boundary_note",
    "home",
    "measured",
    "countries",
}


@pytest.fixture()
def benchmarks() -> dict:
    return load_benchmarks()


# --------------------------------------------------------------------------- #
# Pure builder
# --------------------------------------------------------------------------- #

def test_countries_are_ordered_cleanest_first(benchmarks) -> None:
    out = build_benchmark(benchmarks, "IDN", 0.0, 0.0)
    intensities = [c["intensity"] for c in out["countries"]]
    assert intensities == sorted(intensities)
    # New Zealand at 92.7 gCO2e/kWh is the cleanest grid in the set.
    assert out["countries"][0]["iso3"] == "NZL"
    assert out["countries"][-1]["iso3"] == "MNG"


def test_ranks_are_one_to_n_and_home_rank_is_correct(benchmarks) -> None:
    out = build_benchmark(benchmarks, "IDN", 0.0, 0.0)
    assert [c["rank"] for c in out["countries"]] == list(range(1, len(out["countries"]) + 1))
    assert out["countries"][0]["rank"] == 1  # rank 1 == cleanest
    # Indonesia (705.3 gCO2e/kWh) is 19th of 20 — only Mongolia is dirtier.
    assert out["home"]["iso3"] == "IDN"
    assert out["home"]["rank"] == 19
    assert out["home"]["of"] == 20


def test_delta_pct_is_signed_relative_to_home(benchmarks) -> None:
    out = build_benchmark(benchmarks, "IDN", 0.0, 0.0)
    by_iso = {c["iso3"]: c for c in out["countries"]}
    # Manual: (92.7 - 705.3) / 705.3 * 100 = -86.8566... -> -86.9 (1 dp).
    assert by_iso["NZL"]["delta_pct_vs_home"] == pytest.approx(-86.9, abs=1e-6)
    # A grid dirtier than home is positive; home against itself is zero.
    assert by_iso["MNG"]["delta_pct_vs_home"] > 0
    assert by_iso["IDN"]["delta_pct_vs_home"] == 0.0


def test_counterfactual_arithmetic_is_kwh_times_intensity(benchmarks) -> None:
    kwh = 1_000_000
    measured = 705.3  # == kwh x home intensity / 1e6
    out = build_benchmark(benchmarks, "IDN", kwh, measured)
    by_iso = {c["iso3"]: c for c in out["countries"]}

    # 1_000_000 kWh x 92.7 gCO2e/kWh / 1e6 = 92.7 tCO2e.
    assert by_iso["NZL"]["counterfactual_tco2e"] == pytest.approx(92.7)
    assert by_iso["NZL"]["counterfactual_delta_tco2e"] == pytest.approx(92.7 - 705.3)
    assert by_iso["MNG"]["counterfactual_tco2e"] == pytest.approx(821.8)
    assert by_iso["MNG"]["counterfactual_delta_tco2e"] == pytest.approx(116.5)
    # Home grid reproduces the measured figure exactly -> zero counterfactual delta.
    assert by_iso["IDN"]["counterfactual_tco2e"] == pytest.approx(705.3)
    assert by_iso["IDN"]["counterfactual_delta_tco2e"] == pytest.approx(0.0)

    for country in out["countries"]:
        assert country["counterfactual_tco2e"] == pytest.approx(
            kwh * country["intensity"] / 1_000_000, abs=0.01
        )
        assert country["counterfactual_delta_tco2e"] == pytest.approx(
            country["counterfactual_tco2e"] - measured, abs=0.01
        )


def test_zero_electricity_yields_all_zero_counterfactuals(benchmarks) -> None:
    out = build_benchmark(benchmarks, "IDN", 0.0, 0.0)
    assert out["measured"] == {"electricity_kwh": 0, "tco2e": 0}
    assert all(c["counterfactual_tco2e"] == 0 for c in out["countries"])
    assert all(c["counterfactual_delta_tco2e"] == 0 for c in out["countries"])
    assert len(out["countries"]) == 20


def test_meta_block_is_carried_through_not_hardcoded(benchmarks) -> None:
    meta = benchmarks["meta"]
    out = build_benchmark(benchmarks, "IDN", 0.0, 0.0)
    assert out["basis"] == meta["basis"]
    assert out["unit"] == meta["unit"]
    assert out["source"] == meta["source"]
    assert out["licence"] == meta["licence"]
    assert out["retrieved_via"] == meta["retrieved_via"]
    assert out["boundary_note"]
    assert out["boundary_note"] in meta["boundary_warning"]


# --------------------------------------------------------------------------- #
# HTTP route
# --------------------------------------------------------------------------- #

@pytest.fixture()
def api():
    """TestClient over a fresh app, in-memory session, and a company with usage.

    Not used as a context manager: entering it would run the app lifespan and
    seed the developer's demo database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    seed_emission_factors(session)

    company = Company(name="Test Co", region="ID")
    session.add(company)
    session.commit()
    session.refresh(company)

    ingest_rows(
        session,
        company.id,
        [
            {
                "date": "2026-01-01", "category": "electricity",
                "activity_type": "electricity_kwh", "value": 120_000,
                "unit": "kWh", "cost": 0,
            },
            {
                "date": "2026-02-01", "category": "electricity",
                "activity_type": "electricity_kwh", "value": 80_000,
                "unit": "kWh", "cost": 0,
            },
        ],
    )

    app = FastAPI()
    app.include_router(japac_router.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app), session, company.id
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_router_declares_the_bare_japac_path() -> None:
    assert [route.path for route in japac_router.router.routes] == ["/japac"]


def test_endpoint_returns_the_benchmark_payload(api) -> None:
    client, session, company_id = api

    response = client.get(f"/api/japac?company_id={company_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == TOP_LEVEL_KEYS
    assert set(body["home"]) == {"iso3", "country", "intensity", "year", "rank", "of", "shares_pct"}
    assert set(body["measured"]) == {"electricity_kwh", "tco2e"}
    assert len(body["countries"]) == 20
    assert all(set(c) == COUNTRY_KEYS for c in body["countries"])

    assert body["measured"]["electricity_kwh"] == pytest.approx(200_000)
    # Inventory tonnes come from the curated Scope 2 factor, not the Ember grid.
    factor = resolve_factor(session, "electricity_kwh", "ID")
    assert body["measured"]["tco2e"] == pytest.approx(200_000 * factor.kg_co2e / 1000, rel=1e-3)

    assert body["home"]["iso3"] == "IDN"
    assert body["home"]["of"] == 20

    intensities = [c["intensity"] for c in body["countries"]]
    assert intensities == sorted(intensities)


def test_endpoint_without_electricity_returns_zeros_not_an_error(api) -> None:
    client, session, _ = api

    empty = Company(name="No Power Co", region="ID")
    session.add(empty)
    session.commit()
    session.refresh(empty)

    response = client.get(f"/api/japac?company_id={empty.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["measured"]["electricity_kwh"] == 0
    assert body["measured"]["tco2e"] == 0
    assert all(c["counterfactual_tco2e"] == 0 for c in body["countries"])
    assert all(c["counterfactual_delta_tco2e"] == 0 for c in body["countries"])
