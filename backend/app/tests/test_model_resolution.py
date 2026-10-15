"""Model-id resolution must never land on another vendor's non-text model.

Regression for the Zenmux gateway shape (2026-10-15): models.list() returned
48 ids across vendors, and the ranking picked ``bytedance/doubao-seedream-5.0-flash``
(a video model) for a Gemini chat agent — the generate call then 404'd with
``model_not_supported`` and the agent fell back to the deterministic router
while the UI still claimed Gemini.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.agent.gemini_agent import _resolve_model


class _FakeClient:
    def __init__(self, names: list[str]) -> None:
        self.models = SimpleNamespace(list=lambda: [SimpleNamespace(name=n) for n in names])


GATEWAY_MIX = [
    "google/gemini-4-argon",
    "bytedance/doubao-seedream-5.0-flash",
    "google/gemini-3.8-flash-tts",
    "google/gemini-3.8-flash",
    "qwen/qwen-image-3.0-pro",
    "google/gemini-3.1-flash-lite",
    "google/gemini-2.5-flash",
]


def test_preferred_configured_model_wins_when_listed() -> None:
    client = _FakeClient(GATEWAY_MIX)
    assert _resolve_model(client, "google/gemini-3.1-flash-lite") == "google/gemini-3.1-flash-lite"


def test_bare_preferred_resolves_into_namespace() -> None:
    client = _FakeClient(GATEWAY_MIX)
    assert _resolve_model(client, "gemini-3.1-flash-lite") == "google/gemini-3.1-flash-lite"


def test_fallback_never_leaves_google_namespace_or_picks_media_models() -> None:
    # Preferred id is gone entirely; ranking must not choose the other
    # vendor's video model or Google's own text-to-speech model.
    client = _FakeClient(GATEWAY_MIX)
    chosen = _resolve_model(client, "gemini-9.9-gone")
    assert chosen.startswith("google/")
    assert "tts" not in chosen
    assert "seedream" not in chosen
