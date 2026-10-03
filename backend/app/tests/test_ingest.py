"""Ingestion contract tests.

Two rules the demo now depends on, because the upload screen is the first thing
in the 3-minute script:

* a long-format file carrying both a coarse ``category`` and a precise
  ``activity`` column is read on the precise one — otherwise distinct streams
  collapse into whatever the coarse column happens to name;
* the mapper prefers the more specific keyword, so natural gas does not resolve
  to grid electricity (different scope, ~4x the emission factor).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.engine.calculator import ingest_rows
from app.engine.factors import seed_emission_factors
from app.engine.mapping import infer_activity_type
from app.models import Activity, Company
from app.routers import ingest

# The shape the demo's own electricity.csv uses: a coarse stream column plus a
# precise canonical one, with two different activity types in the same file.
LONG_CSV = (
    "date,category,activity,value,unit,cost\n"
    "2026-01-01,electricity,electricity_kwh,1000,kWh,100\n"
    "2026-01-01,electricity,natural_gas_kwh,500,kWh,50\n"
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    # Rows whose activity type has no factor are skipped, which would hide a
    # mapping bug behind an empty table.
    seed_emission_factors(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def company(db):
    entity = Company(name="Test Co", region="WORLD")
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def test_long_csv_with_both_category_and_activity_maps_each_row_by_activity(db, company) -> None:
    headers, rows = ingest._parse_csv(LONG_CSV)
    mapped = ingest._rows_from_long(headers, rows, {})

    ingest_rows(db, company.id, mapped)

    stored = sorted(row.activity_type for row in db.scalars(select(Activity)).all())
    assert stored == ["electricity_kwh", "natural_gas_kwh"]


def test_preview_reports_every_distinct_activity_not_just_the_coarse_category() -> None:
    preview = ingest._preview(LONG_CSV, "electricity.csv")

    assert {mapping["activity_type"] for mapping in preview["suggested"]} == {
        "electricity_kwh",
        "natural_gas_kwh",
    }


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("natural_gas_kwh", "natural_gas_kwh"),
        ("Natural Gas Consumption", "natural_gas_kwh"),
        ("gas_kwh", "natural_gas_kwh"),
        ("electricity_kwh", "electricity_kwh"),
        ("kwh", "electricity_kwh"),
        ("fuel_litre", "diesel_litre"),
    ],
)
def test_mapper_prefers_the_specific_keyword_over_a_generic_one(column: str, expected: str) -> None:
    assert infer_activity_type(column).activity_type == expected


def test_gas_and_electricity_land_in_different_scopes() -> None:
    assert infer_activity_type("natural_gas_kwh").scope == 1
    assert infer_activity_type("electricity_kwh").scope == 2
