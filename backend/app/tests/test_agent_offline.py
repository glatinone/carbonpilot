"""Offline agent-router regression tests.

The demo's promise is that the LLM never produces a carbon number — it only
*chooses which tool to run* and explains the result. These tests pin that
routing decision for the deterministic offline path, so plain ``pytest -q``
protects the demo from regressing before a live run.

We call ``gemini_agent._offline_chat`` directly rather than ``chat()``:
``chat()`` branches on ambient settings (a dev machine with ``GEMINI_API_KEY``
exported would jump to the network), while the offline router is exactly what
must stay correct and reproducible on any machine. No network, no API key.

Assertion granularity: we assert *which tool family ran*, not the sentence
wording (a wording snapshot would break on any copy-edit). This fails the
moment someone breaks the router's question -> tool mapping.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent import gemini_agent
from app.db import Base
from app.engine.factors import seed_emission_factors
from app.seed import seed_demo


@pytest.fixture(scope="module")
def db() -> Session:
    # Same in-memory pattern as app/tests/test_engine.py, but module-scoped:
    # seeding the 168-row demo dataset plus a ~25s constraint search would
    # otherwise be repeated for every test. The router only reads, so one
    # seeded session is safe to share across the module.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    # seed_demo resolves every activity row to an emission factor; without the
    # factor library first, the whole dataset is skipped and the router would be
    # tested against an empty company.
    seed_emission_factors(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def company_id(db: Session) -> int:
    return int(seed_demo(db)["company_id"])


@pytest.fixture(scope="module")
def routed(db: Session, company_id: int) -> dict[str, dict[str, Any]]:
    """Route each canonical question exactly once through the offline router.

    The constraint-search question enumerates thousands of intervention
    combinations (~tens of seconds); precomputing per question keeps the suite
    fast without weakening any assertion.
    """
    return {
        question: gemini_agent._offline_chat(db, company_id, question)
        for _, question, *_ in CANONICAL_CASES
    }


# question -> (all_of, any_of): the tool family the router must select.
# all_of = every listed tool must run (the demo chains them);
# any_of = at least one equivalent tool must run.
CANONICAL_CASES: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "where-biggest-emissions",
        "Where are our biggest emissions?",
        ("get_baseline", "get_emission_breakdown"),
        (),
    ),
    (
        "why-may-increase",
        "Why did our emissions increase in May 2026?",
        ("detect_anomalies", "explain_anomaly"),
        (),
    ),
    (
        "what-if-cloud-30",
        "What if we reduce cloud usage by 30%?",
        (),
        ("run_scenario", "find_feasible_scenarios"),
    ),
    (
        "what-next",
        "What should we do next?",
        ("list_recommendations",),
        (),
    ),
    (
        "reduce-15-no-cost",
        "Reduce our carbon by 15% without increasing operating cost",
        (),
        ("find_feasible_scenarios",),
    ),
]

CASE_IDS = [case_id for case_id, *_ in CANONICAL_CASES]


def _trace_tools(result: dict[str, Any]) -> list[str]:
    return [str(call.get("tool", "?")) for call in result.get("tool_calls", [])]


@pytest.mark.parametrize(
    ("question", "all_of", "any_of"),
    [(q, all_of, any_of) for _, q, all_of, any_of in CANONICAL_CASES],
    ids=CASE_IDS,
)
def test_offline_router_selects_expected_tool_family(
    routed: dict[str, dict[str, Any]],
    question: str,
    all_of: tuple[str, ...],
    any_of: tuple[str, ...],
) -> None:
    trace = _trace_tools(routed[question])

    missing = [tool for tool in all_of if tool not in trace]
    assert not missing, (
        f"router did not chain the expected tools for {question!r}: "
        f"missing {missing}; expected family {list(all_of) or list(any_of)}; "
        f"actual trace {trace}"
    )

    if any_of:
        assert set(trace) & set(any_of), (
            f"router did not select any scenario tool for {question!r}: "
            f"expected one of {list(any_of)}; actual trace {trace}"
        )


@pytest.mark.parametrize(
    "question",
    [q for _, q, *_ in CANONICAL_CASES],
    ids=CASE_IDS,
)
def test_offline_router_returns_grounded_nonempty_answer(
    routed: dict[str, dict[str, Any]], question: str
) -> None:
    result = routed[question]

    # The recon failure mode: a quantitative answer with no tool call behind it.
    assert result["tool_calls"], (
        f"router answered {question!r} without calling any tool — "
        "the answer would not be grounded in the calculation engine"
    )
    assert str(result.get("answer", "")).strip(), f"router returned an empty answer for {question!r}"
    assert result.get("mode") == "offline"
