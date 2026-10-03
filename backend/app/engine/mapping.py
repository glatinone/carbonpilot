"""Semantic mapping: messy column header -> canonical activity type.

This is the rule-based half of the "Data Understanding Agent". The LLM half
(`app.agent`) asks this module for a suggestion, then explains it. Keeping the
dictionary here means the agent can never hallucinate a unit or a scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# canonical activity_type -> (category, unit, scope, keywords)
CANONICAL: dict[str, dict] = {
    "electricity_kwh": {
        "category": "electricity",
        "unit": "kWh",
        "scope": 2,
        "keywords": [
            "electricity", "electricity_kwh", "electricity_consumed", "electricity_usage",
            "kwh", "power_consumption", "energy_consumption", "grid_electricity",
            "listrik", "purchased_electricity",
        ],
    },
    "natural_gas_kwh": {
        "category": "electricity",
        "unit": "kWh",
        "scope": 1,
        "keywords": ["natural_gas", "gas_consumption", "gas_kwh", "boiler_gas"],
    },
    "cloud_compute_vcpu_hour": {
        "category": "cloud",
        "unit": "vCPU_hours",
        "scope": 3,
        "keywords": [
            "cloud_compute", "vcpu", "vcpu_hour", "vcpu_hours", "compute_hours",
            "instance_hours", "cloud_usage", "cloud_compute_hours", "cpu_hours",
        ],
    },
    "cloud_storage_gb_month": {
        "category": "cloud",
        "unit": "GB_month",
        "scope": 3,
        "keywords": ["cloud_storage", "storage_gb", "gb_month", "storage_usage", "s3_storage"],
    },
    "cloud_network_gb": {
        "category": "cloud",
        "unit": "GB",
        "scope": 3,
        "keywords": ["cloud_network", "data_transfer", "egress", "network_gb", "bandwidth"],
    },
    "flight_passenger_km": {
        "category": "travel",
        "unit": "passenger_km",
        "scope": 3,
        "keywords": [
            "flight", "flight_km", "flight_distance", "flight_passenger_km", "air_travel",
            "passenger_km", "plane", "penerbangan",
        ],
    },
    "train_passenger_km": {
        "category": "travel",
        "unit": "passenger_km",
        "scope": 3,
        "keywords": ["train", "rail", "train_km", "kereta"],
    },
    "car_km": {
        "category": "travel",
        "unit": "km",
        "scope": 3,
        "keywords": ["car_km", "car_distance", "mileage", "taxi", "ride_hailing"],
    },
    "hotel_night": {
        "category": "travel",
        "unit": "room_night",
        "scope": 3,
        "keywords": ["hotel", "hotel_night", "room_night", "accommodation", "nights"],
    },
    "diesel_litre": {
        "category": "fleet",
        "unit": "litre",
        "scope": 1,
        "keywords": [
            "diesel", "diesel_litre", "diesel_usage", "fuel", "fuel_litre", "fuel_usage",
            "fleet_fuel", "bahan_bakar",
        ],
    },
    "petrol_litre": {
        "category": "fleet",
        "unit": "litre",
        "scope": 1,
        "keywords": ["petrol", "gasoline", "bensin", "petrol_litre"],
    },
    "procurement_usd": {
        "category": "procurement",
        "unit": "USD",
        "scope": 3,
        "keywords": ["procurement", "purchase", "spend", "supplier_spend", "pengadaan"],
    },
    "waste_landfill_kg": {
        "category": "other",
        "unit": "kg",
        "scope": 3,
        "keywords": ["waste", "landfill", "waste_kg", "disposal", "sampah"],
    },
    "water_m3": {
        "category": "other",
        "unit": "m3",
        "scope": 3,
        "keywords": ["water", "water_m3", "water_usage", "air"],
    },
}

# Unit aliases -> canonical unit string used by the factor library.
UNIT_ALIASES: dict[str, str] = {
    "kw h": "kWh", "kwh": "kWh", "kilowatt_hour": "kWh", "kilowatt_hours": "kWh", "mwh": "MWh",
    "l": "litre", "liter": "litre", "litre": "litre", "litres": "litre", "liters": "litre",
    "km": "km", "kilometer": "km", "kilometre": "km", "mile": "mile", "miles": "mile",
    "pkm": "passenger_km", "passenger_km": "passenger_km", "passenger-km": "passenger_km",
    "usd": "USD", "idr": "IDR", "sgd": "SGD", "$": "USD",
    "kg": "kg", "tonne": "tonne", "t": "tonne", "m3": "m3", "gb": "GB", "gb_month": "GB_month",
    "vcpu_hours": "vCPU_hours", "vcpu_hour": "vCPU_hours", "vcpu-hours": "vCPU_hours",
    "room_night": "room_night", "night": "room_night", "nights": "room_night",
}


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower()).strip("_")


@dataclass
class MappingResult:
    column: str
    activity_type: str
    category: str
    unit: str
    scope: int
    confidence: float
    rationale: str
    alternatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "column": self.column,
            "activity_type": self.activity_type,
            "category": self.category,
            "unit": self.unit,
            "scope": self.scope,
            "confidence": round(self.confidence, 2),
            "rationale": self.rationale,
            "alternatives": self.alternatives,
        }


def infer_activity_type(column: str, unit: str | None = None) -> MappingResult:
    """Map an arbitrary header to a canonical activity type.

    Exact keyword hits score highest; substring hits score lower. An explicit
    unit match adds confidence and can disambiguate (e.g. "fuel" + "kWh").
    """
    norm = _normalise(column)
    norm_unit = _normalise(unit) if unit else ""

    # Ranked by (score, specificity). Specificity is the length of the matched
    # keyword: a longer keyword explains more of the input, so it is the more
    # precise reading. Without it, ties fall to dict insertion order and the
    # generic "kwh" keyword under electricity outranks "natural_gas" — reading
    # natural gas as grid electricity, wrong scope and ~4x the emission factor.
    best: tuple[float, int, str] | None = None
    runner_up: str | None = None

    for activity_type, spec in CANONICAL.items():
        for keyword in spec["keywords"]:
            if norm == keyword:
                score, specificity = 1.0, len(keyword)
            elif keyword in norm or norm in keyword:
                score, specificity = 0.78, len(keyword)
            else:
                continue

            if norm_unit:
                canonical_unit = _normalise(spec["unit"])
                resolved = _normalise(UNIT_ALIASES.get(norm_unit, norm_unit))
                if resolved == canonical_unit or resolved == norm_unit:
                    score += 0.12
                elif resolved in {"kwh", "mwh"} and canonical_unit == "kwh":
                    score += 0.08

            if best is None or (score, specificity) > (best[0], best[1]):
                runner_up = best[2] if best else None
                best = (score, specificity, activity_type)
            elif runner_up is None:
                runner_up = activity_type

    if best is None:
        # Unknown column: keep the raw name, park it as "other", flag low confidence.
        return MappingResult(
            column=column,
            activity_type=norm or "unknown",
            category="other",
            unit=unit or "",
            scope=3,
            confidence=0.25,
            rationale=(
                f"No canonical match for '{column}'. Treated as Scope 3 'other' — "
                "needs a human-confirmed emission factor before it is calculated."
            ),
        )

    score, _, activity_type = best
    spec = CANONICAL[activity_type]
    confidence = min(score, 0.99)

    unit_note = f" Unit '{unit}' matches the canonical unit '{spec['unit']}'." if norm_unit else ""
    rationale = (
        f"'{column}' resolves to {activity_type} "
        f"({spec['category']}, Scope {spec['scope']}, {spec['unit']}).{unit_note}"
    )

    alternatives = [runner_up] if runner_up and runner_up != activity_type else []

    return MappingResult(
        column=column,
        activity_type=activity_type,
        category=spec["category"],
        unit=spec["unit"],
        scope=spec["scope"],
        confidence=confidence,
        rationale=rationale,
        alternatives=alternatives,
    )


def map_columns(columns: list[str], unit_by_column: dict[str, str] | None = None) -> list[dict]:
    unit_by_column = unit_by_column or {}
    return [infer_activity_type(c, unit_by_column.get(c)).to_dict() for c in columns]
