"""Emissions-intensity contracts — tCO2e per $1M of tracked spend.

The intensity metric is a comparison aid, not a new calculation: it divides the
already-computed footprint by the already-computed spend. It must stay null
when the spend is absent, because a division by zero is a lie, not a number.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.engine import calculator
from app.engine.factors import seed_emission_factors
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


def test_intensity_is_footprint_divided_by_musd(db: Session) -> None:
    result = calculator.baseline(db, 1)
    assert result["intensity_tco2e_per_musd"] is not None
    expected = result["total_tco2e"] / (result["total_cost_usd"] / 1_000_000)
    assert result["intensity_tco2e_per_musd"] == pytest.approx(expected, rel=1e-3)


def test_intensity_is_positive(db: Session) -> None:
    assert calculator.baseline(db, 1)["intensity_tco2e_per_musd"] > 0


def test_intensity_is_null_for_empty_company(db: Session) -> None:
    # Company 2 exists but has no activity rows -> baseline returns incomplete,
    # and the metric must be absent rather than zero/inf.
    baseline = calculator.baseline(db, 2)
    assert baseline["incomplete"] is True
    assert baseline["intensity_tco2e_per_musd"] is None
