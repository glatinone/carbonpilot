"""Climatiq adapter contract tests.

Climatiq is optional and sits off the calculation path, so the risk it carries is
not a wrong demo number — it is code that has never actually run. Every test here
drives the real client against an in-process stub of api.climatiq.io, so request
shape, auth, response parsing and every failure mode are exercised without a key
and without a packet leaving the machine.

What cannot be verified here, and is therefore stated rather than assumed: the
*values* Climatiq returns and whether a given activity_id ranks first for a
query. Those need a live key. Nothing on the demo path depends on them.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.agent import tools
from app.config import get_settings
from app.engine import climatiq


@pytest.fixture(autouse=True)
def _fresh_settings():
    """get_settings is lru_cached; every test needs its own environment."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _closed_port() -> int:
    """A port nothing is listening on, so a connect attempt is refused."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture()
def stub():
    """In-process stand-in for api.climatiq.io, recording every request."""
    captured: list[dict] = []
    responses: dict[tuple[str, str], tuple[int, dict]] = {}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # noqa: ARG002 - silence the test output
            return

        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            parsed = urlparse(self.path)
            captured.append(
                {
                    "method": method,
                    "path": parsed.path,
                    "query": {k: v[0] for k, v in parse_qs(parsed.query).items()},
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": json.loads(raw) if raw else None,
                }
            )
            status, payload = responses.get((method, parsed.path), (200, {"results": []}))
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield SimpleNamespace(
            base_url=f"http://127.0.0.1:{server.server_address[1]}",
            requests=captured,
            respond=lambda m, p, status, payload: responses.__setitem__((m, p), (status, payload)),
        )
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def configured(stub, monkeypatch):
    monkeypatch.setenv("CLIMATIQ_API_KEY", "test-key")
    monkeypatch.setenv("CLIMATIQ_BASE_URL", stub.base_url)
    monkeypatch.setenv("CLIMATIQ_DATA_VERSION", "^33")
    get_settings.cache_clear()
    return stub


# --------------------------------------------------------------------------- #
# Gating
# --------------------------------------------------------------------------- #

def test_without_a_key_nothing_is_sent(monkeypatch) -> None:
    monkeypatch.delenv("CLIMATIQ_API_KEY", raising=False)
    get_settings.cache_clear()

    assert climatiq.is_enabled() is False
    with pytest.raises(climatiq.ClimatiqError, match="CLIMATIQ_API_KEY"):
        climatiq.search("grid electricity")


def test_blank_key_does_not_enable_it(monkeypatch) -> None:
    monkeypatch.setenv("CLIMATIQ_API_KEY", "   ")
    get_settings.cache_clear()
    assert climatiq.is_enabled() is False


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #

def test_search_sends_the_documented_request(configured) -> None:
    configured.respond(
        "GET",
        "/data/v1/search",
        200,
        {
            "results": [
                {
                    "id": "e1",
                    "activity_id": "electricity-supply_grid-source_residual_mix",
                    "name": "Grid electricity",
                    "source": "IEA",
                    "source_dataset": "IEA 2024",
                    "region": "ID",
                    "region_name": "Indonesia",
                    "unit": "kWh",
                    "unit_type": "Energy",
                    "year": 2023,
                    "uncertainty": 12.5,
                    "scopes": ["2"],
                    # present in the real response, dropped by the client
                    "constituent_gases": {"co2": 1.0},
                }
            ],
            "total_results": 41,
        },
    )

    found = climatiq.search("grid electricity", region="ID", limit=3)

    request = configured.requests[-1]
    assert request["method"] == "GET"
    assert request["path"] == "/data/v1/search"
    assert request["headers"]["authorization"] == "Bearer test-key"
    # data_version is required by the API, so it must always be present.
    assert request["query"]["data_version"] == "^33"
    assert request["query"]["query"] == "grid electricity"
    assert request["query"]["region"] == "ID"
    assert request["query"]["results_per_page"] == "3"

    assert found["count"] == 1
    assert found["total_results"] == 41
    assert found["results"][0]["activity_id"] == "electricity-supply_grid-source_residual_mix"
    assert found["results"][0]["source"] == "IEA"
    # Trimmed: the agent gets citation fields, not the whole gas breakdown.
    assert "constituent_gases" not in found["results"][0]


def test_search_refuses_an_empty_query_without_calling_out(configured) -> None:
    with pytest.raises(climatiq.ClimatiqError, match="needs a query"):
        climatiq.search("   ")
    assert configured.requests == []


def test_limit_is_clamped_to_the_documented_maximum(configured) -> None:
    climatiq.search("electricity", limit=9999)
    assert configured.requests[-1]["query"]["results_per_page"] == "25"


# --------------------------------------------------------------------------- #
# Estimate
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("unit", "param", "unit_field", "expected"),
    [
        ("kWh", "energy", "energy_unit", "kWh"),
        ("MWh", "energy", "energy_unit", "MWh"),
        ("kg", "weight", "weight_unit", "kg"),
        ("litre", "volume", "volume_unit", "l"),
        ("km", "distance", "distance_unit", "km"),
        ("USD", "money", "money_unit", "usd"),
    ],
)
def test_estimate_shapes_parameters_per_unit_type(
    configured, unit: str, param: str, unit_field: str, expected: str
) -> None:
    configured.respond(
        "POST",
        "/data/v1/estimate",
        200,
        {
            "co2e": 712.0,
            "co2e_unit": "kg",
            "co2e_calculation_method": "ar6",
            "emission_factor": {"activity_id": "x", "source": "IEA", "year": 2023},
            "constituent_gases": {"co2": 700.0},
            "activity_data": {"activity_value": 1000, "activity_unit": unit},
            "audit_trail": "selector",
            "notices": [],
        },
    )

    result = climatiq.estimate("electricity-supply_grid-source_residual_mix", 1000, unit)

    body = configured.requests[-1]["body"]
    assert body["emission_factor"]["activity_id"] == "electricity-supply_grid-source_residual_mix"
    assert body["emission_factor"]["data_version"] == "^33"
    assert body["parameters"] == {param: 1000, unit_field: expected}

    assert result["co2e"] == 712.0
    assert result["emission_factor"]["source"] == "IEA"
    assert "constituent_gases" not in result


def test_estimate_passes_region_and_year_fallback(configured) -> None:
    configured.respond("POST", "/data/v1/estimate", 200, {"co2e": 1.0})

    climatiq.estimate("x", 5, "kg", region="ID", year=2024)

    selector = configured.requests[-1]["body"]["emission_factor"]
    assert selector["region"] == "ID"
    assert selector["year"] == 2024
    # Without this Climatiq errors rather than picking the nearest year.
    assert selector["year_fallback"] is True


def test_unknown_unit_is_refused_rather_than_guessed(configured) -> None:
    with pytest.raises(climatiq.ClimatiqError, match="vCPU_hours"):
        climatiq.estimate("x", 5, "vCPU_hours")
    assert configured.requests == []


# --------------------------------------------------------------------------- #
# Failure modes: every one must become ClimatiqError, never an exception that
# escapes into a request path.
# --------------------------------------------------------------------------- #

def test_api_error_becomes_a_typed_error(configured) -> None:
    configured.respond("GET", "/data/v1/search", 400, {"error": "bad_request", "message": "unknown data_version"})

    with pytest.raises(climatiq.ClimatiqError) as excinfo:
        climatiq.search("electricity")
    assert "400" in str(excinfo.value)
    assert "unknown data_version" in str(excinfo.value)


def test_unreachable_host_becomes_a_typed_error(monkeypatch) -> None:
    monkeypatch.setenv("CLIMATIQ_API_KEY", "test-key")
    monkeypatch.setenv("CLIMATIQ_BASE_URL", f"http://127.0.0.1:{_closed_port()}")
    get_settings.cache_clear()

    with pytest.raises(climatiq.ClimatiqError, match="unreachable"):
        climatiq.search("electricity")


def test_unauthorized_is_surfaced(configured) -> None:
    configured.respond("GET", "/data/v1/search", 401, {"error": "unauthorized"})
    with pytest.raises(climatiq.ClimatiqError) as excinfo:
        climatiq.search("electricity")
    assert "401" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# The agent tool: same guarantees, but it must never raise at all.
# --------------------------------------------------------------------------- #

def test_tool_reports_plainly_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("CLIMATIQ_API_KEY", raising=False)
    get_settings.cache_clear()

    result = tools.tool_lookup_live_factor(None, 1, "grid electricity")

    assert result["enabled"] is False
    assert "CLIMATIQ_API_KEY" in result["message"]
    assert "search_emission_factors" in result["message"]  # points at the fallback
    assert tools.summarize("lookup_live_factor", result) == "live factor lookup not configured"


def test_tool_returns_live_results_and_an_estimate(configured) -> None:
    configured.respond(
        "GET",
        "/data/v1/search",
        200,
        {"results": [{"activity_id": "electricity-supply_grid-source_residual_mix", "source": "IEA"}]},
    )
    configured.respond("POST", "/data/v1/estimate", 200, {"co2e": 712.0, "co2e_unit": "kg"})

    result = tools.tool_lookup_live_factor(
        None, 1, "grid electricity", region="ID", value=1000, unit="kWh"
    )

    assert result["enabled"] is True
    assert result["count"] == 1
    assert result["estimate"]["co2e"] == 712.0
    assert tools.summarize("lookup_live_factor", result).startswith("1 live factor")


def test_tool_swallows_an_api_failure(configured) -> None:
    configured.respond("GET", "/data/v1/search", 500, {"error": "server_error"})

    result = tools.tool_lookup_live_factor(None, 1, "grid electricity")

    assert result["enabled"] is True
    assert "500" in result["error"]
    assert tools.summarize("lookup_live_factor", result).startswith("lookup_live_factor:")


def test_tool_survives_a_failed_estimate(configured) -> None:
    configured.respond(
        "GET", "/data/v1/search", 200, {"results": [{"activity_id": "x", "source": "IEA"}]}
    )
    configured.respond("POST", "/data/v1/estimate", 400, {"message": "unsupported unit"})

    result = tools.tool_lookup_live_factor(None, 1, "grid electricity", value=1, unit="kWh")

    # The search still succeeded, so the caller keeps the citation.
    assert result["count"] == 1
    assert "unsupported unit" in result["estimate_error"]