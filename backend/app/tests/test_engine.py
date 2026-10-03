"""Engine tests — behaviour contracts, not snapshots.

Each test asserts a relationship between two pieces of data (activity x factor,
anomaly vs baseline, constraint satisfaction) rather than a frozen number.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.engine import anomaly, calculator, mapping, scenario
from app.engine.factors import resolve_factor, seed_emission_factors
from app.engine.recommender import generate as generate_recommendations
from app.models import Company


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    seed_emission_factors(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def company(db) -> Company:
    entity = Company(name="Test Co", region="WORLD")
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# --------------------------------------------------------------------------- #
# Semantic mapping
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("electricity_kwh", "electricity_kwh"),
        ("Electricity Consumed", "electricity_kwh"),
        ("cloud_compute_hours", "cloud_compute_vcpu_hour"),
        ("vcpu_hours", "cloud_compute_vcpu_hour"),
        ("flight_km", "flight_passenger_km"),
        ("diesel_usage", "diesel_litre"),
        ("fuel_litre", "diesel_litre"),
        ("procurement_spend", "procurement_usd"),
    ],
)
def test_column_mapping_resolves_canonical_types(column: str, expected: str) -> None:
    assert mapping.infer_activity_type(column).activity_type == expected


def test_unknown_column_is_flagged_low_confidence_not_guessed() -> None:
    result = mapping.infer_activity_type("mystery_metric_xyz")
    assert result.confidence < 0.5
    assert result.category == "other"


def test_unit_disambiguates_similar_headers() -> None:
    with_unit = mapping.infer_activity_type("consumption", "kWh")
    without_unit = mapping.infer_activity_type("consumption")
    assert with_unit.confidence >= without_unit.confidence


# --------------------------------------------------------------------------- #
# Calculation engine
# --------------------------------------------------------------------------- #

def test_calculation_equals_activity_times_factor(db, company) -> None:
    """The core contract: co2e == value x factor, and scope comes from the factor."""
    calculator.ingest_rows(
        db,
        company.id,
        [
            {
                "date": "2026-01-01",
                "category": "electricity",
                "activity_type": "electricity_kwh",
                "value": 10_000,
                "unit": "kWh",
                "cost": 1_100,
            }
        ],
    )

    factor = resolve_factor(db, "electricity_kwh", "WORLD")
    base = calculator.baseline(db, company.id)

    assert base["total_tco2e"] == pytest.approx(10_000 * factor.kg_co2e / 1000, rel=1e-6)
    assert base["scope_split"]["scope_2"]["tco2e"] == pytest.approx(base["total_tco2e"])
    assert base["total_cost_usd"] == pytest.approx(1_100)


def test_unknown_activity_type_is_skipped_not_invented(db, company) -> None:
    result = calculator.ingest_rows(
        db,
        company.id,
        [
            {
                "date": "2026-01-01",
                "category": "other",
                "activity_type": "not_a_real_stream",
                "value": 5,
                "unit": "x",
                "cost": 0,
            }
        ],
    )
    assert result["activities_created"] == 0
    assert result["rows_skipped"] == 1
    assert calculator.baseline(db, company.id)["total_tco2e"] == 0


def test_negative_values_are_rejected(db, company) -> None:
    result = calculator.ingest_rows(
        db,
        company.id,
        [
            {
                "date": "2026-01-01",
                "category": "electricity",
                "activity_type": "electricity_kwh",
                "value": -100,
                "unit": "kWh",
                "cost": 0,
            }
        ],
    )
    assert result["rows_skipped"] == 1


def test_recalculate_is_idempotent(db, company) -> None:
    calculator.ingest_rows(
        db,
        company.id,
        [
            {
                "date": "2026-02-01",
                "category": "cloud",
                "activity_type": "cloud_compute_vcpu_hour",
                "value": 1_000_000,
                "unit": "vCPU_hours",
                "cost": 21_000,
            }
        ],
    )
    first = calculator.baseline(db, company.id)["total_tco2e"]
    calculator.recalculate(db, company.id)
    calculator.recalculate(db, company.id)
    assert calculator.baseline(db, company.id)["total_tco2e"] == pytest.approx(first)


def test_breakdown_percentages_sum_to_100(db, company) -> None:
    calculator.ingest_rows(
        db,
        company.id,
        [
            {
                "date": "2026-01-01", "category": "electricity",
                "activity_type": "electricity_kwh", "value": 5_000, "unit": "kWh", "cost": 0,
            },
            {
                "date": "2026-01-01", "category": "fleet",
                "activity_type": "diesel_litre", "value": 1_000, "unit": "litre", "cost": 0,
            },
            {
                "date": "2026-01-01", "category": "travel",
                "activity_type": "flight_passenger_km", "value": 20_000,
                "unit": "passenger_km", "cost": 0,
            },
        ],
    )
    rows = calculator.breakdown(db, company.id, by="category")
    assert sum(r["pct"] for r in rows) == pytest.approx(100.0, abs=0.4)


# --------------------------------------------------------------------------- #
# Anomaly detection
# --------------------------------------------------------------------------- #

def _monthly_cloud_rows(values: dict[str, float]) -> list[dict]:
    return [
        {
            "date": f"{month}-01",
            "category": "cloud",
            "activity_type": "cloud_compute_vcpu_hour",
            "value": value,
            "unit": "vCPU_hours",
            "cost": value * 0.021,
        }
        for month, value in values.items()
    ]


def test_anomaly_detector_finds_the_injected_spike(db, company) -> None:
    """A single spike must not hide itself by inflating the spread (why MAD)."""
    values = {
        "2026-01": 4_200_000, "2026-02": 4_500_000, "2026-03": 4_300_000,
        "2026-04": 4_700_000, "2026-05": 12_900_000, "2026-06": 4_800_000,
        "2026-07": 4_600_000, "2026-08": 4_400_000,
    }
    calculator.ingest_rows(db, company.id, _monthly_cloud_rows(values))

    found = anomaly.detect(db, company.id)
    months = {a["month"] for a in found}
    assert "2026-05" in months
    assert all(a["direction"] == "spike" for a in found if a["month"] == "2026-05")


def test_flat_series_produces_no_anomalies(db, company) -> None:
    flat = {f"2026-{m:02d}": 4_000_000 for m in range(1, 9)}
    calculator.ingest_rows(db, company.id, _monthly_cloud_rows(flat))
    assert anomaly.detect(db, company.id) == []


def test_explain_attributes_the_weekend_driver(db, company) -> None:
    rows = _monthly_cloud_rows({f"2026-{m:02d}": 4_000_000 for m in range(1, 7)})
    rows.append(
        {
            "date": "2026-05-01", "category": "cloud",
            "activity_type": "cloud_compute_vcpu_hour",
            "value": 11_000_000, "unit": "vCPU_hours", "cost": 231_000,
            "meta": {"month": "2026-05", "weekend_share": 0.62},
        }
    )
    for row in rows[:-1]:
        row["meta"] = {"month": row["date"][:7], "weekend_share": 0.15}
    calculator.ingest_rows(db, company.id, rows)

    detail = anomaly.explain(db, company.id, "2026-05", "cloud_compute_vcpu_hour")
    assert detail["drivers"], "expected an attributed driver"
    assert detail["drivers"][0]["observed"] > detail["drivers"][0]["baseline"]


# --------------------------------------------------------------------------- #
# Scenario engine
# --------------------------------------------------------------------------- #

def _seed_two_streams(db, company) -> None:
    calculator.ingest_rows(
        db,
        company.id,
        _monthly_cloud_rows({f"2026-{m:02d}": 4_000_000 for m in range(1, 13)})
        + [
            {
                "date": f"2026-{m:02d}-01",
                "category": "electricity",
                "activity_type": "electricity_kwh",
                "value": 350_000,
                "unit": "kWh",
                "cost": 40_250,
            }
            for m in range(1, 13)
        ],
    )


def test_scenario_reduction_is_linear_in_the_requested_percentage(db, company) -> None:
    _seed_two_streams(db, company)
    half = scenario.run_scenario(
        db, company.id, [{"activity_type": "electricity_kwh", "reduction_pct": 10}]
    )
    full = scenario.run_scenario(
        db, company.id, [{"activity_type": "electricity_kwh", "reduction_pct": 20}]
    )
    assert full["impact"]["carbon_saving_tco2e"] == pytest.approx(
        half["impact"]["carbon_saving_tco2e"] * 2, rel=1e-6
    )


def test_scenario_never_drives_emissions_below_zero(db, company) -> None:
    _seed_two_streams(db, company)
    result = scenario.run_scenario(
        db, company.id, [{"activity_type": "electricity_kwh", "reduction_pct": 100}]
    )
    assert result["projected"]["total_tco2e"] >= 0
    assert result["impact"]["carbon_reduction_pct"] <= 100.0


def test_scenario_preserves_total_by_construction(db, company) -> None:
    """Projected + saved must equal the baseline — no double counting."""
    _seed_two_streams(db, company)
    result = scenario.run_scenario(
        db, company.id, [{"activity_type": "cloud_compute_vcpu_hour", "reduction_pct": 30}]
    )
    assert result["projected"]["total_tco2e"] + result["impact"]["carbon_saving_tco2e"] == (
        pytest.approx(result["baseline"]["total_tco2e"], rel=1e-6)
    )


def test_unknown_activity_type_in_scenario_is_reported_not_silently_dropped(db, company) -> None:
    _seed_two_streams(db, company)
    result = scenario.run_scenario(
        db, company.id, [{"activity_type": "made_up_stream", "reduction_pct": 50}]
    )
    assert result["per_intervention"][0].get("error")


def test_constraint_search_only_returns_satisfying_scenarios(db, company) -> None:
    _seed_two_streams(db, company)
    search = scenario.find_feasible(
        db, company.id, min_carbon_reduction_pct=10.0, max_cost_increase_usd=0.0
    )
    assert search["scenarios_evaluated"] > 0
    for item in search["feasible"]:
        assert item["carbon_reduction_pct"] >= 10.0
        assert item["cost_delta_usd"] <= 0.0


def test_constraint_search_prefers_recommended_scenario_when_feasible_exists(db, company) -> None:
    _seed_two_streams(db, company)
    search = scenario.find_feasible(
        db, company.id, min_carbon_reduction_pct=5.0, max_cost_increase_usd=0.0
    )
    if search["feasible"]:
        assert search["recommended"] is not None
        assert search["recommended"]["feasible"] is True


# --------------------------------------------------------------------------- #
# Recommender
# --------------------------------------------------------------------------- #

def test_recommendations_are_ranked_and_grounded(db, company) -> None:
    _seed_two_streams(db, company)
    recs = generate_recommendations(db, company.id)

    assert recs, "expected at least one recommendation"
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)

    for rec in recs:
        assert rec.carbon_impact_t >= 0
        assert rec.effort in {"low", "medium", "high"}
        assert 0 <= rec.confidence_pct <= 100
        # Every recommendation must carry its own evidence trail.
        assert rec.evidence.get("method") == "activity_data x emission_factor"


def test_confidence_reflects_factor_uncertainty(db, company) -> None:
    """A high-uncertainty factor (cloud) must not out-score a precise one (diesel)."""
    _seed_two_streams(db, company)
    calculator.ingest_rows(
        db,
        company.id,
        [
            {
                "date": f"2026-{m:02d}-01", "category": "fleet",
                "activity_type": "diesel_litre", "value": 30_000, "unit": "litre", "cost": 33_000,
            }
            for m in range(1, 13)
        ],
    )
    recs = generate_recommendations(db, company.id)
    by_type = {r.activity_type: r for r in recs}
    if "cloud_compute_vcpu_hour" in by_type and "diesel_litre" in by_type:
        assert by_type["cloud_compute_vcpu_hour"].confidence_pct < by_type["diesel_litre"].confidence_pct


# --------------------------------------------------------------------------- #
# Demo dataset integrity
# --------------------------------------------------------------------------- #

def test_demo_dataset_is_coherent_and_detectable(db, company) -> None:
    """The shipped demo data must actually contain the anomaly the pitch demos."""
    from app.seed import generate_rows

    rows = [r for r in generate_rows() if r["activity_type"] == "cloud_compute_vcpu_hour"]
    assert len(rows) == 12

    values = [r["value"] for r in rows]
    assert max(values) > 2 * sorted(values)[len(values) // 2], "May spike missing"

    calculator.ingest_rows(db, company.id, generate_rows())
    found = anomaly.detect(db, company.id)
    months = {a["month"] for a in found}
    assert "2026-05" in months


def test_demo_dataset_covers_all_three_scopes(db, company) -> None:
    from app.seed import generate_rows

    calculator.ingest_rows(db, company.id, generate_rows())
    base = calculator.baseline(db, company.id)
    assert {"scope_1", "scope_2", "scope_3"} <= set(base["scope_split"])
