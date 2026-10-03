"""Pre-presentation preflight for the CarbonPilot demo.

Run this immediately before walking on stage. It exercises the exact surface the
judges will see — every API route behind the four pages, the constraint search,
and one real agent question — and fails loudly rather than letting a dead
endpoint, an exhausted LLM key, or a 30-second stall be discovered mid-demo.

Read-only against the running API except for ``--reset``, which re-seeds the
synthetic dataset from scratch.

    ./.venv/Scripts/python.exe scripts/preflight.py
    ./.venv/Scripts/python.exe scripts/preflight.py --reset
    ./.venv/Scripts/python.exe scripts/preflight.py --base-url http://127.0.0.1:3000

Exit code 0 = ready to present, 1 = something would break on stage.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# The question the demo script actually asks in front of an audience.
CANONICAL_QUESTION = "Why did our emissions increase in May 2026?"

# Two rows, two different activity types, one shared coarse `category`. This is
# the shape the demo's own electricity.csv uses, and it is the shape that hid a
# mapping bug: natural gas must not collapse into grid electricity.
SAMPLE_CSV = (
    "date,category,activity,value,unit,cost\n"
    "2026-01-01,electricity,electricity_kwh,1000,kWh,100\n"
    "2026-01-01,electricity,natural_gas_kwh,500,kWh,50\n"
)

# A constraint search slower than this is dead air the audience will feel.
SLOW_SEARCH_SECONDS = 5.0

BACKEND_DIR = Path(__file__).resolve().parents[1]

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"


class Result:
    def __init__(self, name: str, status: str, detail: str) -> None:
        self.name, self.status, self.detail = name, status, detail


def _get(base: str, path: str, timeout: float = 60.0):
    with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as response:
        return response.status, json.load(response)


def _post(base: str, path: str, payload: dict, timeout: float = 300.0):
    request = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.load(response)


def _post_multipart(base: str, path: str, filename: str, content: str, timeout: float = 60.0):
    """POST a small CSV the way the upload screen does — as a real multipart body."""
    boundary = "----carbonpilot-preflight"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/csv\r\n\r\n{content}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    request = urllib.request.Request(
        f"{base}{path}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.load(response)


def _check(results: list[Result], name: str, fn) -> None:
    """Run one check, converting an exception into a FAIL instead of a traceback."""
    try:
        results.append(fn())
    except urllib.error.HTTPError as exc:
        results.append(Result(name, FAIL, f"HTTP {exc.code}"))
    except Exception as exc:  # noqa: BLE001 - every failure is a finding to report
        results.append(Result(name, FAIL, f"{type(exc).__name__}: {exc}"))


def _reset_demo_data() -> Result:
    """Re-seed the synthetic dataset so actions and scenario history start clean."""
    proc = subprocess.run(
        [sys.executable, "-m", "app.seed", "--seed-db"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or [""]
        return Result("reset demo data", FAIL, tail[0])
    return Result("reset demo data", OK, "re-seeded")


def build_checks(base: str) -> list[Result]:
    results: list[Result] = []

    def health() -> Result:
        _, data = _get(base, "/api/health")
        mode = data.get("llm_mode")
        if mode != "gemini":
            return Result(
                "health / LLM",
                WARN,
                f"llm_mode={mode} — the agent will answer from the deterministic router and the "
                "UI will label it 'Deterministic engine'. Add a key or accept it out loud.",
            )
        return Result(
            "health / LLM",
            OK,
            f"mode=gemini model={data.get('llm_model_resolved') or data.get('llm_model')}",
        )

    def ui() -> Result:
        _, data = _get(base, "/api/health")
        if data.get("ui_served"):
            return Result("health / UI", OK, "static export served from the API port")
        return Result(
            "health / UI",
            OK,
            "not served here — fine in dev mode (Next.js on :3000 provides the pages)",
        )

    def dashboard() -> Result:
        _, data = _get(base, "/api/dashboard")
        base_data = data["baseline"]
        return Result(
            "dashboard",
            OK if base_data["activity_count"] else FAIL,
            f"{base_data['total_tco2e']:,.0f} tCO2e / {base_data['activity_count']} rows / "
            f"{len(data['insights'])} insights / {data['opportunity_count']} opportunities",
        )

    def non_empty(name: str, path: str, key: str) -> Result:
        _, data = _get(base, path)
        items = data.get(key) or []
        return Result(
            name,
            OK if items else FAIL,
            f"{len(items)} entries" if items else f"empty — the page will render blank ({path})",
        )

    def actions() -> Result:
        _, data = _get(base, "/api/actions")
        count = data.get("count", 0)
        if count:
            return Result(
                "action plan",
                WARN,
                f"{count} stale action(s) from a rehearsal — run with --reset to clear them",
            )
        return Result("action plan", OK, "clean (0 actions)")

    def constraint_search() -> Result:
        started = time.time()
        _, data = _post(
            base,
            "/api/scenarios/constraints",
            {"min_carbon_reduction_pct": 15, "max_cost_increase_usd": 0},
        )
        elapsed = time.time() - started
        detail = (
            f"{len(data.get('feasible', []))} feasible / {data.get('scenarios_evaluated')} "
            f"evaluated in {elapsed:.1f}s"
        )
        if elapsed > SLOW_SEARCH_SECONDS:
            return Result("constraint search", WARN, f"{detail} — that is visible dead air on stage")
        return Result("constraint search", OK, detail)

    def upload() -> Result:
        _, data = _post_multipart(base, "/api/ingest/preview", "preflight.csv", SAMPLE_CSV)
        types = sorted({m["activity_type"] for m in data.get("suggested", [])})
        if not types:
            return Result("upload / mapping", FAIL, "nothing was mapped — the upload screen shows an empty table")
        if len(types) < 2:
            return Result(
                "upload / mapping",
                FAIL,
                f"distinct streams collapsed into {types} — check the name-column preference "
                "and the keyword specificity tiebreak",
            )
        return Result("upload / mapping", OK, f"preview maps {len(types)} activity types: {types}")

    def agent() -> Result:
        started = time.time()
        _, data = _post(base, "/api/chat", {"message": CANONICAL_QUESTION, "company_id": 1})
        elapsed = time.time() - started
        tools = [call.get("tool") for call in data.get("tool_calls") or []]
        if not tools:
            return Result(
                "agent (Ask panel)",
                FAIL,
                "answered with no tool call — the number would not be grounded",
            )
        if not str(data.get("answer", "")).strip():
            return Result("agent (Ask panel)", FAIL, "empty answer")
        return Result(
            "agent (Ask panel)",
            OK,
            f"mode={data.get('mode')} tools={tools} in {elapsed:.1f}s",
        )

    _check(results, "health / LLM", health)
    _check(results, "health / UI", ui)
    _check(results, "dashboard", dashboard)
    _check(results, "insights", lambda: non_empty("insights", "/api/insights", "insights"))
    _check(
        results,
        "interventions",
        lambda: non_empty("interventions", "/api/interventions", "interventions"),
    )
    _check(
        results,
        "recommendations",
        lambda: non_empty("recommendations", "/api/recommendations", "recommendations"),
    )
    _check(results, "action plan", actions)
    _check(results, "upload / mapping", upload)
    _check(results, "constraint search", constraint_search)
    _check(results, "agent (Ask panel)", agent)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-presentation preflight for CarbonPilot.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008", help="API base URL.")
    parser.add_argument(
        "--reset", action="store_true", help="Re-seed the demo dataset before checking."
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print(f"CarbonPilot preflight — {base}\n")
    results: list[Result] = []
    if args.reset:
        _check(results, "reset demo data", _reset_demo_data)

    results.extend(build_checks(base))

    failed = 0
    for result in results:
        if result.status == FAIL:
            failed += 1
        print(f"  {result.status:<4} {result.name:<20} {result.detail}")

    warned = sum(1 for r in results if r.status == WARN)
    print()
    if failed:
        print(f"NOT READY — {failed} check(s) failed. Fix before presenting.")
        return 1
    if warned:
        print(f"READY with {warned} warning(s) — read them out or fix them.")
        return 0
    print("READY — all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())