"""A failed model call must be visible, never silently absorbed.

The agent degrades to the deterministic router on purpose, and the degraded answer
is still correct — real numbers, real tool calls, real citations. That is exactly
why a broken key can survive an entire deployment without anyone noticing: nothing
looks wrong, the answers simply stopped being explained by the model.

This surfaced for real. A gateway key was rejected because the endpoint override
lived only in .env, the SDK fell back to Google's own host, and the deployed agent
quietly answered from the router while `/api/health` still reported `llm_mode:
gemini` — a claim derived from the key merely being present.

`last_error()` is what turns that back into an observable fact: `/api/health`
reports it and `preflight` fails on it. These are the contracts that keep it true.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agent import gemini_agent


@pytest.fixture(autouse=True)
def _reset_agent_state():
    """The agent records its last failure in a module global. Without this, one test
    leaves state for the next and the suite becomes order-dependent."""
    gemini_agent._LAST_ERROR = None
    gemini_agent._RESOLVED_MODEL = None
    yield
    gemini_agent._LAST_ERROR = None


OFFLINE = {
    "answer": "from the deterministic engine",
    "mode": "offline",
    "tool_calls": [{"tool": "get_emission_breakdown", "args": {}, "summary": "s"}],
    "grounded": True,
    "model": None,
}


def _settings(**overrides):
    base = {"llm_enabled": True, "llm_key": "k", "gemini_model": "m", "gemini_base_url": ""}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_failed_model_call_is_recorded_and_says_so_in_the_answer():
    with (
        patch.object(gemini_agent, "get_settings", return_value=_settings()),
        patch.object(gemini_agent, "_gemini_chat", side_effect=RuntimeError("API_KEY_INVALID")),
        patch.object(gemini_agent, "_offline_chat", return_value=dict(OFFLINE)),
    ):
        result = gemini_agent.chat(db=None, company_id=1, message="why?")

    assert result["mode"] == "offline"
    # The operator-facing answer must carry the reason, not just the numbers.
    assert "Falling back" in result["answer"]
    assert "API_KEY_INVALID" in result["answer"]
    # And the machine-readable record must exist for /api/health and preflight.
    err = gemini_agent.last_error()
    assert err is not None
    assert "API_KEY_INVALID" in err


def test_successful_model_call_clears_a_previous_error():
    with (
        patch.object(gemini_agent, "get_settings", return_value=_settings()),
        patch.object(
            gemini_agent,
            "_gemini_chat",
            return_value={
                "answer": "ok",
                "mode": "gemini",
                "tool_calls": [],
                "grounded": True,
                "model": "m",
            },
        ),
        patch.object(gemini_agent, "_offline_chat", return_value=dict(OFFLINE)),
    ):
        result = gemini_agent.chat(db=None, company_id=1, message="why?")

    assert result["mode"] == "gemini"
    assert gemini_agent.last_error() is None


def test_no_key_is_not_an_error():
    """Running without a key is a supported mode, so it must not be reported as a
    failure — otherwise the signal becomes noise and gets ignored."""
    with (
        patch.object(gemini_agent, "get_settings", return_value=_settings(llm_enabled=False)),
        patch.object(gemini_agent, "_offline_chat", return_value=dict(OFFLINE)),
    ):
        gemini_agent.chat(db=None, company_id=1, message="why?")
        assert gemini_agent.last_error() is None


def test_error_record_is_truncated_because_it_is_surfaced_in_health():
    """A provider error is often a wall of JSON; health has to stay readable."""
    wall = "x" * 5000
    with (
        patch.object(gemini_agent, "get_settings", return_value=_settings()),
        patch.object(gemini_agent, "_gemini_chat", side_effect=RuntimeError(wall)),
        patch.object(gemini_agent, "_offline_chat", return_value=dict(OFFLINE)),
    ):
        gemini_agent.chat(db=None, company_id=1, message="why?")

    err = gemini_agent.last_error()
    assert err is not None
    assert len(err) <= 300
