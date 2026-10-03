"""Synthetic demo dataset — a coherent 12-month operating history.

Design goals:
  * physically consistent (activity data x real emission factors)
  * contains deliberate anomalies so the AI has something to *find*
  * ships as CSV files in the shape the demo uploads

Company: PT Nusantara Digital, an Indonesian digital-services group
(offices + warehouses + a real cloud estate + a delivery fleet).
"""

from __future__ import annotations

import csv
import random
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.engine.calculator import ingest_rows
from app.models import ActionItem, Activity, Calculation, Company, Recommendation, ScenarioRecord

COMPANY_NAME = "PT Nusantara Digital"
COMPANY_REGION = "ID"
YEAR = 2026
MONTHS = list(range(1, 13))

RNG_SEED = 20261004

# activity_type -> baseline monthly spec
#   value      : typical monthly activity
#   unit       : canonical unit
#   unit_cost  : USD per unit
#   category   : rollup bucket
#   weekend    : typical share of the activity happening at the weekend
#   seasonality: month -> multiplier (mild, non-anomalous)
#   anomaly    : month -> (multiplier, weekend_share_override)
PROFILE: dict[str, dict] = {
    "electricity_kwh": {
        "value": 350_000, "unit": "kWh", "unit_cost": 0.115, "category": "electricity",
        "seasonality": {3: 1.02, 4: 1.05, 5: 1.06, 6: 1.04, 7: 1.07, 8: 1.09, 9: 1.05},
    },
    "natural_gas_kwh": {
        "value": 60_000, "unit": "kWh", "unit_cost": 0.05, "category": "electricity",
        "seasonality": {7: 1.10, 8: 1.12, 9: 1.06},
    },
    "cloud_compute_vcpu_hour": {
        "value": 40_000_000, "unit": "vCPU_hours", "unit_cost": 0.021, "category": "cloud",
        "weekend": 0.15,
        # May: an untracked batch job quadrupled weekend usage.
        "anomaly": {5: (2.75, 0.62)},
    },
    "cloud_storage_gb_month": {
        "value": 900_000, "unit": "GB_month", "unit_cost": 0.023, "category": "cloud",
        "growth": 0.012,
    },
    "cloud_network_gb": {
        "value": 60_000, "unit": "GB", "unit_cost": 0.09, "category": "cloud",
    },
    "flight_passenger_km": {
        "value": 500_000, "unit": "passenger_km", "unit_cost": 0.30, "category": "travel",
        "seasonality": {3: 1.15, 6: 1.10, 9: 1.08, 11: 1.12},
    },
    "hotel_night": {
        "value": 600, "unit": "room_night", "unit_cost": 180.0, "category": "travel",
        "seasonality": {3: 1.15, 6: 1.10, 9: 1.08},
    },
    "car_km": {
        "value": 40_000, "unit": "km", "unit_cost": 0.45, "category": "travel",
    },
    "train_passenger_km": {
        "value": 80_000, "unit": "passenger_km", "unit_cost": 0.08, "category": "travel",
    },
    "diesel_litre": {
        "value": 30_000, "unit": "litre", "unit_cost": 1.10, "category": "fleet",
        # September: a distribution surge drove an extra 60%.
        "anomaly": {9: (1.60, None)},
    },
    "petrol_litre": {
        "value": 8_000, "unit": "litre", "unit_cost": 1.20, "category": "fleet",
    },
    "procurement_usd": {
        "value": 1_500_000, "unit": "USD", "unit_cost": 1.0, "category": "procurement",
        "growth": 0.008,
    },
    "waste_landfill_kg": {
        "value": 20_000, "unit": "kg", "unit_cost": 0.05, "category": "other",
    },
    "water_m3": {
        "value": 8_000, "unit": "m3", "unit_cost": 1.20, "category": "other",
    },
}

# Which CSV file each activity type ships in (mirrors the demo's upload story).
CSV_GROUP: dict[str, str] = {
    "electricity_kwh": "electricity.csv",
    "natural_gas_kwh": "electricity.csv",
    "cloud_compute_vcpu_hour": "cloud_usage.csv",
    "cloud_storage_gb_month": "cloud_usage.csv",
    "cloud_network_gb": "cloud_usage.csv",
    "flight_passenger_km": "travel.csv",
    "hotel_night": "travel.csv",
    "car_km": "travel.csv",
    "train_passenger_km": "travel.csv",
    "diesel_litre": "fuel.csv",
    "petrol_litre": "fuel.csv",
    "procurement_usd": "procurement.csv",
    "waste_landfill_kg": "procurement.csv",
    "water_m3": "procurement.csv",
}


def generate_rows(seed: int = RNG_SEED) -> list[dict]:
    """Build the 12-month activity dataset, anomalies included."""
    rng = random.Random(seed)
    rows: list[dict] = []

    for activity_type, spec in PROFILE.items():
        base = float(spec["value"])
        for month in MONTHS:
            multiplier = 1.0
            multiplier *= spec.get("seasonality", {}).get(month, 1.0)
            # Compounding growth for slowly expanding streams.
            multiplier *= (1 + spec.get("growth", 0.0)) ** (month - 1)

            weekend_share = spec.get("weekend")
            anomaly = spec.get("anomaly", {}).get(month)
            if anomaly:
                multiplier *= anomaly[0]
                if anomaly[1] is not None:
                    weekend_share = anomaly[1]

            noise = 1 + rng.uniform(-0.035, 0.035)
            value = base * multiplier * noise
            value = round(value, 2) if value < 10_000 else round(value)

            meta: dict = {"month": f"{YEAR}-{month:02d}"}
            if weekend_share is not None:
                meta["weekend_share"] = round(
                    weekend_share * (1 + rng.uniform(-0.06, 0.06)), 3
                )

            rows.append(
                {
                    "date": date(YEAR, month, 1).isoformat(),
                    "category": spec["category"],
                    "activity_type": activity_type,
                    "value": value,
                    "unit": spec["unit"],
                    "cost": round(value * spec["unit_cost"], 2),
                    "source": CSV_GROUP[activity_type],
                    "meta": meta,
                }
            )

    return rows


def write_csvs(output_dir: Path) -> list[Path]:
    """Write the demo upload files. Header shape matches the pitch deck."""
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict]] = {}
    for row in generate_rows():
        grouped.setdefault(CSV_GROUP[row["activity_type"]], []).append(row)

    written: list[Path] = []
    for filename, rows in sorted(grouped.items()):
        path = output_dir / filename
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["date", "category", "activity", "value", "unit", "cost"])
            for row in rows:
                writer.writerow(
                    [
                        row["date"],
                        row["category"],
                        row["activity_type"],
                        row["value"],
                        row["unit"],
                        row["cost"],
                    ]
                )
        written.append(path)
    return written


def get_or_create_company(db: Session, name: str = COMPANY_NAME, region: str = COMPANY_REGION) -> Company:
    company = db.scalar(select(Company).where(Company.name == name))
    if company:
        return company
    company = Company(name=name, region=region)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def reset_company(db: Session, company: Company) -> None:
    db.execute(
        delete(Calculation).where(
            Calculation.activity_id.in_(
                select(Activity.id).where(Activity.company_id == company.id)
            )
        )
    )
    db.execute(delete(ActionItem).where(ActionItem.company_id == company.id))
    db.execute(delete(Recommendation).where(Recommendation.company_id == company.id))
    db.execute(delete(ScenarioRecord).where(ScenarioRecord.company_id == company.id))
    db.execute(delete(Activity).where(Activity.company_id == company.id))
    db.commit()


def seed_demo(db: Session, reset: bool = True) -> dict:
    """Create the demo company with 12 months of activity and calculated results."""
    from app.engine.recommender import generate as generate_recommendations

    company = get_or_create_company(db)
    if reset:
        reset_company(db, company)

    result = ingest_rows(db, company.id, generate_rows())
    recommendations = generate_recommendations(db, company.id, replace=True)

    return {
        "company_id": company.id,
        "company": company.name,
        "region": company.region,
        "activities_created": result["activities_created"],
        "rows_skipped": result["rows_skipped"],
        "recommendations": len(recommendations),
    }


if __name__ == "__main__":  # pragma: no cover - manual helper
    import argparse

    parser = argparse.ArgumentParser(description="CarbonPilot demo data tools")
    parser.add_argument("--csv", type=Path, help="Directory to write demo CSVs into")
    parser.add_argument("--seed-db", action="store_true", help="Seed the configured database")
    args = parser.parse_args()

    if args.csv:
        for path in write_csvs(args.csv):
            print(f"wrote {path}")
    if args.seed_db:
        from app.db import SessionLocal, init_db

        init_db()
        with SessionLocal() as session:
            print(seed_demo(session))
