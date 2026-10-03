#!/usr/bin/env python
"""Agent evaluation harness for the CarbonPilot demo path.

Why this exists
---------------
During rehearsal the agent sometimes answered a *quantitative* question without
calling a single tool (it replied "Which May do you mean?" with an empty
``tool_calls`` trace), while the same question against the same data produced the
correct ``['detect_anomalies', 'explain_anomaly']`` trace. That non-determinism is
the most visible thing that can go wrong in front of judges.

The product's central promise is that the LLM never produces a carbon number — it
only *chooses which tool to run* and explains the result. So the regression
contract this harness pins is exactly the decision the agent must make: **which
tool family it selects** for each canonical judge question. If that mapping
breaks, the harness fails loudly.

Offline by default
------------------
A default run needs no network and no API key: it asserts against
``gemini_agent._offline_chat`` (the deterministic router) directly rather than
going through ``chat()``, whose Gemini-vs-offline branch depends on ambient
settings (a dev machine with ``GEMINI_API_KEY`` exported would hit the network).
``--live`` is opt-in and exercises the real ``chat()`` path when a key is present.

Isolation
---------
The harness seeds its OWN throwaway SQLite database under ``tempfile`` and never
touches ``backend/carbonpilot.db``.

Usage (from ``backend/``)::

    .venv/Scripts/python.exe scripts/eval_agent.py          # offline (default)
    .venv/Scripts/python.exe scripts/eval_agent.py --live    # real Gemini path
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

# Running as ``python scripts/eval_agent.py`` puts ``scripts/`` (not the backend
# root) on sys.path, so ``import app`` would fail. Add the backend root first.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.agent import gemini_agent  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402
from app.engine.factors import seed_emission_factors  # noqa: E402
from app.seed import seed_demo  # noqa: E402


# --------------------------------------------------------------------------- #
# Canonical demo cases
# --------------------------------------------------------------------------- #
# Each case names the tool *family* that must appear in the returned trace.
# ``all_of`` = every listed tool must be called (the demo chains them);
# ``any_of`` = at least one listed tool must be called (equivalent tools).
#
# Wording is taken from DEMO.md where the demo script supplies it.
CANONICAL_CASES: list[dict[str, Any]] = [
    {
        "case": "1",
        "question": "Where are our biggest emissions?",
        "all_of": ("get_baseline", "get_emission_breakdown"),
        "any_of": (),
    },
    {
        "case": "2",
        "question": "Why did our emissions increase in May 2026?",
        "all_of": ("detect_anomalies", "explain_anomaly"),
        "any_of": (),
    },
    {
        "case": "3",
        "question": "What if we reduce cloud usage by 30%?",
        "all_of": (),
        "any_of": ("run_scenario", "find_feasible_scenarios"),
    },
    {
        "case": "4",
        "question": "What should we do next?",
        "all_of": ("list_recommendations",),
        "any_of": (),
    },
    {
        "case": "5",
        "question": "Reduce our carbon by 15% without increasing operating cost",
        "all_of": (),
        "any_of": ("find_feasible_scenarios",),
    },
]


# --------------------------------------------------------------------------- #
# Seeded throwaway database
# --------------------------------------------------------------------------- #

def build_seeded_session(tmpdir: str) -> tuple[Session, int, Any]:
    """Create a fresh SQLite DB inside ``tmpdir`` and seed the demo dataset.

    Also seeds the emission-factor library first: ``seed_demo`` resolves every
    activity row to a factor, so without it the whole dataset is skipped and the
    router would see an empty company (a false PASS waiting to happen).
    """
    db_path = Path(tmpdir) / "eval_agent.db"
    # Guard the isolation contract: never the production database.
    assert db_path.resolve() != (BACKEND_DIR / "carbonpilot.db").resolve()

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    seed_emission_factors(session)
    info = seed_demo(session)
    return session, int(info["company_id"]), engine


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #

def _trace_tools(result: dict) -> list[str]:
    return [str(call.get("tool", "?")) for call in result.get("tool_calls", [])]


def check_case(case: dict, result: dict) -> tuple[bool, str]:
    """Return (passed, failure_reason). Empty reason means PASS."""
    trace = _trace_tools(result)
    trace_set = set(trace)

    missing_all = [t for t in case["all_of"] if t not in trace_set]
    missing_any = bool(case["any_of"]) and not (trace_set & set(case["any_of"]))
    answer_empty = not str(result.get("answer", "")).strip()

    if not (missing_all or missing_any or answer_empty):
        return True, ""

    expected = ", ".join(case["all_of"]) or " | ".join(case["any_of"])
    parts: list[str] = []
    if missing_all:
        parts.append(f"missing tool(s): {', '.join(missing_all)}")
    if missing_any:
        parts.append(f"none of the scenario tools ran: {', '.join(case['any_of'])}")
    if answer_empty:
        parts.append("answer was empty")
    return False, (
        f"case {case['case']} ({case['question']!r}) FAILED: {'; '.join(parts)}. "
        f"expected tools [{expected}], actual trace {trace}"
    )


def _print_table(rows: list[list[str]]) -> None:
    headers = ["#", "RESULT", "QUESTION", "EXPECTED TOOLS", "ACTUAL TRACE"]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def line(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    print(line(headers))
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    for row in rows:
        print(line(row))


def evaluate(call_fn: Callable[[str], dict]) -> int:
    """Run every canonical case through ``call_fn``; print table; return exit code."""
    rows: list[list[str]] = []
    failures: list[str] = []

    for case in CANONICAL_CASES:
        result = call_fn(case["question"])
        passed, reason = check_case(case, result)
        if not passed:
            failures.append(reason)
        expected = ", ".join(case["all_of"]) or " | ".join(case["any_of"])
        trace = ", ".join(_trace_tools(result)) or "(none)"
        rows.append(
            [
                case["case"],
                "PASS" if passed else "FAIL",
                case["question"],
                expected,
                trace,
            ]
        )

    _print_table(rows)
    print()

    if failures:
        for reason in failures:
            print(f"FAILURE: {reason}")
        print(
            f"\n{len(CANONICAL_CASES) - len(failures)}/{len(CANONICAL_CASES)} cases passed "
            f"— {len(failures)} FAILED."
        )
        return 1

    print(f"{len(CANONICAL_CASES)}/{len(CANONICAL_CASES)} cases passed.")
    return 0


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CarbonPilot agent eval harness")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Exercise the real Gemini chat() path (needs an API key; hits the network).",
    )
    args = parser.parse_args(argv)

    if args.live and not get_settings().llm_enabled:
        print(
            "--live requested but no Gemini API key is configured "
            "(set GEMINI_API_KEY or GOOGLE_API_KEY). Refusing to run the live path.",
            file=sys.stderr,
        )
        return 2

    mode = "gemini (live)" if args.live else "offline (deterministic)"
    print(f"CarbonPilot agent eval — mode: {mode}\n")

    with tempfile.TemporaryDirectory(prefix="carbonpilot_eval_") as tmpdir:
        db, company_id, engine = build_seeded_session(tmpdir)
        try:
            def call_fn(question: str) -> dict:
                if args.live:
                    return gemini_agent.chat(db, company_id, question)
                # Direct call: independent of ambient settings, no network, no key.
                return gemini_agent._offline_chat(db, company_id, question)

            return evaluate(call_fn)
        finally:
            db.close()
            engine.dispose()


if __name__ == "__main__":  # pragma: no cover - manual/CI entry point
    raise SystemExit(main())
