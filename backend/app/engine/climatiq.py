"""Live emission factors from Climatiq — optional, opt-in, off the demo path.

``app/engine/factors.py`` stays the source of truth for every number the demo
shows. Pinning a rehearsed presentation to a third party's live data would let a
remote change move the figures mid-demo, so Climatiq is a *corroboration* layer
instead: the agent can pull the current published factor and cite it beside the
curated one, and a judge asking "are these real?" gets a live answer.

Discipline borrowed from the factor library: nothing here raises into a request
path. A missing key, a timeout, a 4xx or a malformed body all become
``ClimatiqError``, which the tool layer turns into ``{"error": ...}``.

Two endpoints, both documented at climatiq.io/docs/api-reference:

* ``GET  /data/v1/search``    — find factors (requires ``data_version``)
* ``POST /data/v1/estimate``  — activity data x factor -> kgCO2e

Resolution goes through *search* rather than hardcoded activity ids: ids churn
and carry a required data version, so asking Climatiq for the best match is both
more robust and honest about who decided which factor applies.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("carbonpilot.climatiq")


class ClimatiqError(RuntimeError):
    """Any reason a live lookup could not be completed. Never fatal."""


# Climatiq names the estimate parameters after the unit *type* of the factor, so
# the request body differs per stream. Only the types this product actually
# handles are listed; anything else is refused rather than guessed at.
_UNIT_PARAMETERS: dict[str, tuple[str, str, dict[str, str]]] = {
    "energy": ("energy", "energy_unit", {"kwh": "kWh", "mwh": "MWh", "gwh": "GWh"}),
    "weight": ("weight", "weight_unit", {"kg": "kg", "t": "t", "tonne": "t", "lb": "lb"}),
    "volume": ("volume", "volume_unit", {"l": "l", "litre": "l", "liter": "l", "m3": "m3"}),
    "distance": ("distance", "distance_unit", {"km": "km", "mi": "mi", "mile": "mi"}),
    "money": ("money", "money_unit", {"usd": "usd", "idr": "idr", "gbp": "gbp", "eur": "eur"}),
}

# Kept out of the estimate response: hundreds of bytes of gas breakdown the
# agent cannot use and the model should not be handed.
_ESTIMATE_KEEP = (
    "co2e",
    "co2e_unit",
    "co2e_calculation_method",
    "co2e_calculation_origin",
    "activity_data",
    "audit_trail",
    "notices",
)
_FACTOR_KEEP = ("name", "activity_id", "source", "source_dataset", "year", "region", "scopes")


def is_enabled() -> bool:
    """True when a Climatiq key is configured."""
    return get_settings().climatiq_enabled


def _request_parameters(value: float, unit: str) -> dict[str, Any]:
    """Translate ``(value, unit)`` into Climatiq's unit-type-shaped parameters."""
    key = unit.strip().lower()
    for param, unit_field, aliases in _UNIT_PARAMETERS.values():
        resolved = aliases.get(key, key if key in aliases.values() else None)
        if resolved:
            return {param: value, unit_field: resolved}
    raise ClimatiqError(
        f"Unit {unit!r} is not one this client maps to a Climatiq parameter. "
        f"Known units: "
        + ", ".join(sorted({u for _, _, a in _UNIT_PARAMETERS.values() for u in a}))
    )


def _call(method: str, path: str, **kwargs) -> dict:
    settings = get_settings()
    if not settings.climatiq_enabled:
        raise ClimatiqError("No CLIMATIQ_API_KEY configured.")

    url = f"{settings.climatiq_base_url.rstrip('/')}{path}"
    try:
        with httpx.Client(timeout=settings.climatiq_timeout_s) as client:
            response = client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {settings.climatiq_api_key.strip()}"},
                **kwargs,
            )
    except httpx.HTTPError as exc:  # connectivity, DNS, timeout
        raise ClimatiqError(f"Climatiq unreachable: {type(exc).__name__}") from exc

    if response.status_code >= 400:
        # Climatiq returns {"error": "...", "message": "..."} on a bad request.
        detail = ""
        try:
            body = response.json()
            detail = str(body.get("message") or body.get("error") or "")
        except Exception:  # noqa: BLE001 - a non-JSON error body is still an error
            detail = response.text[:200]
        raise ClimatiqError(f"Climatiq {response.status_code}: {detail or 'request rejected'}")

    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001
        raise ClimatiqError(f"Climatiq returned a non-JSON body: {exc}") from exc


def _trim_factor(result: dict) -> dict:
    return {key: result.get(key) for key in _FACTOR_KEEP if result.get(key) is not None}


def search(
    query: str,
    *,
    region: str | None = None,
    year: int | None = None,
    limit: int = 5,
) -> dict:
    """Find the emission factors that best match a free-text query."""
    if not query or not query.strip():
        raise ClimatiqError("A search needs a query.")

    settings = get_settings()
    params: dict[str, Any] = {
        "data_version": settings.climatiq_data_version,
        "query": query.strip(),
        "results_per_page": max(1, min(limit, 25)),
    }
    if region:
        params["region"] = region
    if year:
        params["year"] = year

    body = _call("GET", "/data/v1/search", params=params)
    results = [_trim_factor(item) for item in (body.get("results") or [])]
    return {
        "query": query,
        "data_version": settings.climatiq_data_version,
        "count": len(results),
        "total_results": body.get("total_results"),
        "results": results,
    }


def estimate(
    activity_id: str,
    value: float,
    unit: str,
    *,
    region: str | None = None,
    year: int | None = None,
) -> dict:
    """Calculate kgCO2e for activity data against a Climatiq factor."""
    settings = get_settings()
    selector: dict[str, Any] = {
        "activity_id": activity_id,
        "data_version": settings.climatiq_data_version,
    }
    if region:
        selector["region"] = region
    if year:
        selector["year"] = year
        # Without this Climatiq errors instead of picking the nearest year.
        selector["year_fallback"] = True

    body = _call(
        "POST",
        "/data/v1/estimate",
        json={"emission_factor": selector, "parameters": _request_parameters(value, unit)},
    )
    payload = {key: body.get(key) for key in _ESTIMATE_KEEP}
    payload["emission_factor"] = _trim_factor(body.get("emission_factor") or {})
    return payload