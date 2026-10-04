"""JAPAC grid-intensity benchmarking.

Two responsibilities, kept apart on purpose:

* :func:`build_benchmark` is a **pure** function — no DB, no network, no file
  I/O — that turns the shipped benchmark document into the response the
  ``/japac`` endpoint returns. It is what the tests exercise directly.
* two thin adapters read the shipped benchmark file and the company's measured
  electricity from the *existing* calculation engine.

Boundary discipline
-------------------
The shipped JAPAC numbers are Ember **full-lifecycle** CO2e intensities used
for comparison only. They are never mixed into the company's reported
inventory: ``measured.tco2e`` comes from the curated Scope 2 factor library via
``app.engine.calculator``, so the two methodologies stay separate.
"""

from __future__ import annotations

import json
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.engine import calculator

BENCHMARKS_PATH = DATA_DIR / "japac_grid_benchmarks.json"

# Company.region is a short code ("ID", "SG", ...); the benchmark set is keyed
# by ISO-3166 alpha-3. Covers the JAPAC set the benchmark ships.
_REGION_TO_ISO3 = {
    "NZ": "NZL",
    "PK": "PAK",
    "LK": "LKA",
    "KR": "KOR",
    "VN": "VNM",
    "JP": "JPN",
    "SG": "SGP",
    "KH": "KHM",
    "MM": "MMR",
    "AU": "AUS",
    "CN": "CHN",
    "TH": "THA",
    "PH": "PHL",
    "MY": "MYS",
    "TW": "TWN",
    "IN": "IND",
    "HK": "HKG",
    "BD": "BGD",
    "ID": "IDN",
    "MN": "MNG",
}

# The demo company is Indonesian; when nothing in the company row maps to a
# benchmark country we fall back here rather than inventing a home.
DEFAULT_HOME_ISO3 = "IDN"


@lru_cache
def load_benchmarks() -> dict:
    """Read the shipped benchmark document (meta block + country rows)."""
    with BENCHMARKS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def home_iso3_for_region(region: str | None, available: set[str] | None = None) -> str:
    """Resolve a company's home country to an ISO-3 code in the benchmark set.

    ``region`` may already be an ISO-3 (it is matched against ``available``
    first), a JAPAC alpha-2 code, or anything else — in which case the
    documented default applies.
    """
    key = (region or "").strip().upper()
    if available and key in available:
        return key
    return _REGION_TO_ISO3.get(key, DEFAULT_HOME_ISO3)


def measured_electricity(db: Session, company_id: int) -> tuple[float, float]:
    """(kWh, tCO2e) of the company's measured purchased electricity.

    Reuses the engine's own ``Activity``-join rather than re-querying, and sums
    the *stored* calculation (activity x inventory factor) so the reported
    tonnes follow the same method as the rest of the app.
    """
    rows = calculator._joined(db, company_id)
    kwh = 0.0
    kg = 0.0
    for activity, calculation, _factor in rows:
        if activity.activity_type == "electricity_kwh":
            kwh += activity.value
            kg += calculation.co2e_kg
    return kwh, kg / calculator.KG_PER_TONNE


def _boundary_note(meta: dict) -> str:
    """One sentence from the benchmark's boundary warning.

    Kept to a single sentence so it can sit next to the numbers without a wall
    of text; the full warning still travels in the source document.
    """
    text = (meta.get("boundary_warning") or "").strip()
    if not text:
        return ""
    end = text.find(". ")
    return text[: end + 1] if end != -1 else text


def build_benchmark(
    benchmarks: dict,
    home_iso3: str,
    electricity_kwh: float,
    measured_tco2e: float,
) -> dict:
    """Build the lifecycle-benchmark payload. Pure — safe to unit-test directly.

    ``countries`` are ordered cleanest-grid first (rank 1 = lowest intensity).
    ``delta_pct_vs_home`` is signed relative to the home grid, so a negative
    value means a country is cleaner than home. ``counterfactual_*`` answers
    "what would this electricity have emitted on that grid", using the
    comparison intensity only.
    """
    meta = benchmarks.get("meta", {})
    rows = sorted(
        benchmarks.get("countries", []),
        key=lambda c: c["carbon_intensity_gco2_kwh"],
    )
    of = len(rows)
    ranks = {c["iso3"]: i for i, c in enumerate(rows, start=1)}

    kwh = round(float(electricity_kwh or 0.0), 2)
    measured = round(float(measured_tco2e or 0.0), 2)

    home = next((c for c in rows if c["iso3"] == home_iso3), None)
    if home is None:
        # Unknown home: fall back to the cleanest row so the payload still
        # forms rather than erroring. The router keeps homes in the set.
        home = rows[0]
    home_intensity = float(home["carbon_intensity_gco2_kwh"])

    def country_row(country: dict) -> dict:
        intensity = float(country["carbon_intensity_gco2_kwh"])
        counterfactual = round(kwh * intensity / 1_000_000, 2)
        delta_pct = (
            round((intensity - home_intensity) / home_intensity * 100, 1)
            if home_intensity
            else 0.0
        )
        return {
            "iso3": country["iso3"],
            "country": country["country"],
            "intensity": intensity,
            "year": country["year"],
            "rank": ranks[country["iso3"]],
            "shares_pct": country.get("shares_pct", {}),
            "delta_pct_vs_home": delta_pct,
            "counterfactual_tco2e": counterfactual,
            "counterfactual_delta_tco2e": round(counterfactual - measured, 2),
        }

    return {
        "basis": meta.get("basis"),
        "unit": meta.get("unit"),
        "source": meta.get("source"),
        "retrieved_via": meta.get("retrieved_via"),
        "licence": meta.get("licence"),
        "boundary_note": _boundary_note(meta),
        "home": {
            "iso3": home["iso3"],
            "country": home["country"],
            "intensity": home_intensity,
            "year": home["year"],
            "rank": ranks[home["iso3"]],
            "of": of,
            "shares_pct": home.get("shares_pct", {}),
        },
        "measured": {"electricity_kwh": kwh, "tco2e": measured},
        "countries": [country_row(c) for c in rows],
    }
