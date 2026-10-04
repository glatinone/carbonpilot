"""Gemini tool-calling agent.

Design contract (this is also the pitch line):

    The LLM interprets data, chooses which analytical tool to run, and explains
    the result. It never produces a carbon number — the calculation engine does.

When no API key is configured the agent falls back to a deterministic router so
the demo still runs end to end (clearly labelled `mode="offline"`).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agent import tools
from app.config import get_settings

MAX_STEPS = 6

# Model id the agent actually ran with. Gateways namespace model ids (e.g.
# `google/gemini-2.5-flash`), so the model that ends up being called is not
# always the one configured — /api/health reports both so they are never
# confused for each other.
_RESOLVED_MODEL: str | None = None


def resolved_model() -> str | None:
    """Last model id the agent actually called, or None before the first call."""
    return _RESOLVED_MODEL

SYSTEM_INSTRUCTION = """You are CarbonPilot, a carbon decision engine for sustainability and operations managers.

RULES (non-negotiable):
1. NEVER invent a carbon number, cost figure, or emission factor. Every number you state must come from a tool result.
2. Always call at least one tool before answering, even when the question is ambiguous. If the period, unit or scope is unclear, call a tool to establish it (get_monthly_series lists the months that exist) rather than asking the user to clarify.
   - "why" / "what happened" → detect_anomalies, then explain_anomaly for the top result (always attribute the driver, not just the magnitude)
   - "what if" / "reduce by X%" → find_feasible_scenarios when a constraint is given, run_scenario otherwise
   - "what should we do" → list_recommendations
   - "how much / total / breakdown" → get_baseline, then get_emission_breakdown
   - "how is this calculated / what is the method / which scope" → search_methodology
3. After tool results come back, answer in at most 5 sentences. Lead with the number, then the driver, then the recommended action.
4. Always state the assumption behind an estimate and the confidence level when you present an estimate.
5. Mention the emission factor source when you cite a factor.
6. If a tool returns an error, adapt and try a different tool or argument rather than guessing.
7. When you explain HOW a figure was derived, or which scope/method applies, ground the explanation in search_methodology and cite the passage's source and section. Do not explain methodology from your own recollection when a retrieved passage covers it.
8. If asked whether the emission factors are real, current, or commercially sourced, call lookup_live_factor and report exactly what it returns. The curated factor library remains the source of truth for this company's reported numbers; a live factor corroborates it, it does not replace it.

You are advising an operations manager who must justify spend to their CFO: give them carbon impact, financial impact, effort and confidence together.
"""


def _json_default(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _dumps(payload: Any) -> str:
    return json.dumps(payload, default=_json_default)


def _is_not_found(exc: Exception) -> bool:
    """Model-id errors surface as a 404/NotFound from the API, not a config error."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 404:
        return True
    text = str(exc).lower()
    return "404" in text or "not_found" in text or "not found" in text


def _resolve_model(client, preferred: str) -> str:
    """Pick a usable model id.

    Model ids churn, and gateways namespace them (e.g. `google/gemini-2.5-flash`),
    so a hardcoded default goes stale. If the configured id is not in the account's
    list, fall back to the closest available flash model.
    """
    try:
        available = [m.name for m in client.models.list()]
    except Exception:  # noqa: BLE001 - listing is best-effort
        return preferred

    if not available or preferred in available:
        return preferred

    # Same model, different namespace (strip/add a vendor prefix).
    bare = preferred.split("/")[-1]
    for name in available:
        if name.split("/")[-1] == bare:
            return name

    # Otherwise take the newest-looking non-specialised flash model.
    def rank(name: str) -> tuple:
        lowered = name.lower()
        penalised = any(
            token in lowered for token in ("image", "tts", "audio", "embedding", "veo", "imagen")
        )
        return (penalised, "preview" in lowered, "flash" not in lowered, name)

    return sorted(available, key=rank)[0]


# --------------------------------------------------------------------------- #
# Gemini path
# --------------------------------------------------------------------------- #

def _gemini_chat(db: Session, company_id: int, message: str) -> dict:
    global _RESOLVED_MODEL

    from google import genai
    from google.genai import types

    settings = get_settings()

    # The SDK resolves its base URL from the process environment, not from our
    # Settings object (see config.gemini_base_url). Export it before the client is
    # built, or a .env-only endpoint override is silently ignored and the key gets
    # sent to the wrong host.
    if settings.gemini_base_url.strip():
        os.environ.setdefault("GOOGLE_GEMINI_BASE_URL", settings.gemini_base_url.strip())

    client = genai.Client(api_key=settings.llm_key)
    model = _resolve_model(client, settings.gemini_model)

    declarations = [
        types.FunctionDeclaration(
            name=name,
            description=spec["description"],
            parameters=spec["parameters"],
        )
        for name, spec in tools.TOOLS.items()
    ]

    def build_config(mode: types.FunctionCallingConfigMode) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[types.Tool(function_declarations=declarations)],
            temperature=0.2,
            # The first step is forced to call a tool. Left on AUTO the model
            # sometimes answers a quantitative question from its own head, or
            # asks for a clarification it could have looked up — the one
            # failure mode that breaks the product's central promise.
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=mode)
            ),
        )

    contents: list[Any] = [types.Content(role="user", parts=[types.Part(text=message)])]
    trace: list[dict] = []
    answer = ""

    for step in range(MAX_STEPS):
        config = build_config(
            types.FunctionCallingConfigMode.ANY
            if step == 0
            else types.FunctionCallingConfigMode.AUTO
        )
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as exc:  # noqa: BLE001
            if not _is_not_found(exc):
                raise
            # Configured model rejected: resolve a working one once, then retry.
            resolved = _resolve_model(client, model)
            if resolved == model:
                raise
            model = resolved
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )

        _RESOLVED_MODEL = model
        calls = getattr(response, "function_calls", None) or []
        if not calls:
            answer = (getattr(response, "text", "") or "").strip()
            break

        contents.append(response.candidates[0].content)

        response_parts = []
        for call in calls:
            args = dict(call.args or {})
            result = tools.dispatch(db, company_id, call.name, args)
            trace.append(
                {
                    "tool": call.name,
                    "args": args,
                    "summary": tools.summarize(call.name, result),
                }
            )
            response_parts.append(
                types.Part.from_function_response(
                    name=call.name, response={"result": _dumps(result)}
                )
            )
        contents.append(types.Content(role="user", parts=response_parts))
    else:
        answer = (
            "I ran several analyses but did not converge on an answer. "
            "Try narrowing the question (one activity type, one month)."
        )

    if not answer:
        answer = "No answer was produced. Please rephrase the question."

    return {
        "answer": answer,
        "tool_calls": trace,
        "grounded": True,
        "mode": "gemini",
        "model": model,
    }


# --------------------------------------------------------------------------- #
# Offline deterministic fallback
# --------------------------------------------------------------------------- #

_CATEGORY_HINTS = {
    "cloud": "cloud",
    "compute": "cloud",
    "server": "cloud",
    "electricity": "electricity",
    "energy": "electricity",
    "office": "electricity",
    "travel": "travel",
    "flight": "travel",
    "hotel": "travel",
    "fleet": "fleet",
    "diesel": "fleet",
    "fuel": "fleet",
    "procurement": "procurement",
    "supplier": "procurement",
    "waste": "other",
    "water": "other",
}


# Intent cues for the offline router. Matched on word boundaries with their
# inflections, because plain substring tests quietly miss the natural phrasings
# the demo actually uses: "reduce our carbon by 15%" has an object between the
# verb and "by", and "increase" is not a substring of "increasing".
_REDUCTION_RE = re.compile(
    r"\b(reduce|reducing|cut|cutting|lower|lowering|decrease|decreasing"
    r"|shrink|kurangi|turunkan)\b"
)
_COST_CONSTRAINT_RE = re.compile(
    r"(without (increasing|raising|adding)|no (additional|extra) cost"
    r"|tanpa (menambah|menaikkan|nambah))"
)
_REASON_RE = re.compile(
    r"\b(why|kenapa|reason|driver|drivers|increas\w*|rise|rising|rose|spike|naik)\b"
)


def _offline_chat(db: Session, company_id: int, message: str) -> dict:
    """Rule-based stand-in so the product is demoable without an API key."""
    text = message.lower()
    trace: list[dict] = []

    def call(name: str, args: dict | None = None) -> dict:
        result = tools.dispatch(db, company_id, name, args or {})
        trace.append({"tool": name, "args": args or {}, "summary": tools.summarize(name, result)})
        return result

    month_match = re.search(r"(20\d{2})[-/ ]?(0[1-9]|1[0-2])", message)
    month = None
    if month_match:
        month = f"{month_match.group(1)}-{month_match.group(2)}"

    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", message)
    percent = float(pct_match.group(1)) if pct_match else None

    category = next((v for k, v in _CATEGORY_HINTS.items() if k in text), None)
    wants_reason = _REASON_RE.search(text) is not None
    wants_action = any(k in text for k in ["should we do", "recommend", "action", "priorit", "what can we"])
    wants_explain = any(k in text for k in ["how much", "total", "footprint", "baseline", "berapa", "emission"])

    # The demo's headline question — "reduce our carbon by 15% without
    # increasing operating cost" — matches no fixed phrase, so the intent is
    # detected from its parts: a reduction verb together with a target or a cost
    # ceiling. The constraint branch must also win over the reason branch when
    # both fire, because that sentence contains the word "increasing".
    cost_ceiling = _COST_CONSTRAINT_RE.search(text) is not None
    wants_constraint = percent is not None and _REDUCTION_RE.search(text) is not None
    wants_whatif = any(k in text for k in ["what if", "what-if", "simulate", "scenario"])

    lines: list[str] = []

    if cost_ceiling or wants_constraint or (wants_whatif and percent):
        target = percent if percent is not None else 10.0
        constraints = call(
            "find_feasible_scenarios",
            {"min_carbon_reduction_pct": target, "max_cost_increase_usd": 0},
        )
        best = constraints.get("recommended")
        if best:
            lines.append(
                f"To cut at least {target:.0f}% of emissions without raising cost, "
                f"the best combination is: {best['label']}."
            )
            lines.append(
                f"Estimated impact: -{best['carbon_saving_tco2e']:,.0f} tCO2e/year "
                f"({best['carbon_reduction_pct']:.1f}%), cost change "
                f"{best['cost_delta_usd']:+,.0f} USD/year, effort {best['effort']}, "
                f"confidence {best['confidence_pct']:.0f}%."
            )
        else:
            lines.append(constraints.get("message", "No feasible scenario found."))
            closest = constraints.get("infeasible", [])[:1]
            if closest:
                lines.append(
                    f"Closest option: {closest[0]['label']} → "
                    f"{closest[0]['carbon_reduction_pct']:.1f}% carbon, "
                    f"{closest[0]['cost_delta_usd']:+,.0f} USD/year."
                )
        lines.append("Assumptions: reductions scale linearly with activity; emission factors held constant.")

    elif wants_reason:
        anomalies = call("detect_anomalies", {})
        items = anomalies.get("anomalies", [])
        if not items:
            lines.append("No statistical anomalies in the recorded monthly series.")
        else:
            if month:
                top = next((a for a in items if a["month"] == month), None) or max(
                    items, key=lambda a: abs(a["z_score"])
                )
            else:
                # Without a month, the standout is the most statistically extreme
                # move, not the one with the largest absolute tonne delta.
                top = max(items, key=lambda a: abs(a["z_score"]))
            detail = call(
                "explain_anomaly",
                {"month": top["month"], "activity_type": top["activity_type"]},
            )
            lines.append(
                f"{top['month']}: {top['activity_type'].replace('_', ' ')} moved "
                f"{top['change_pct']:+.1f}% versus the recent baseline "
                f"({top['value_tco2e']:.1f} vs {top['baseline_tco2e']:.1f} tCO2e)."
            )
            for driver in detail.get("drivers", [])[:2]:
                lines.append(driver["description"])
            if detail.get("activity_change"):
                change = detail["activity_change"]
                lines.append(
                    f"Contribution: {change['delta_tco2e']:+.1f} tCO2e "
                    f"({change['change_pct']:+.1f}%)."
                )
        lines.append("Method: robust median/MAD z-score over the monthly series.")

    elif wants_action:
        recs = call("list_recommendations", {})
        items = recs.get("recommendations", [])[:3]
        if not items:
            lines.append("Not enough activity data to rank actions yet.")
        else:
            lines.append("Top prioritised actions (carbon x cost x effort):")
            for rec in items:
                lines.append(
                    f"  • {rec['title']} — {rec['carbon_impact_t']:,.0f} tCO2e/year, "
                    f"{rec['cost_impact_usd']:+,.0f} USD/year, effort {rec['effort']}, "
                    f"confidence {rec['confidence_pct']:.0f}%."
                )
            lines.append("Every figure is traceable to source activity data and emission factors.")

    else:
        base = call("get_baseline", {})
        lines.append(
            f"Total footprint: {base['total_tco2e']:,.0f} tCO2e over "
            f"{base.get('month_count')} months "
            f"(avg {base.get('avg_monthly_tco2e', 0):,.0f} tCO2e/month), "
            f"operating cost {base['total_cost_usd']:,.0f} USD."
        )
        split = base.get("scope_split", {})
        if split:
            parts = ", ".join(
                f"{k.replace('_', ' ').title()} {v['pct']:.0f}%" for k, v in split.items()
            )
            lines.append(f"Scope split: {parts}.")
        breakdown = call("get_emission_breakdown", {"by": "category"})
        rows = breakdown.get("rows", [])[:4]
        if rows:
            lines.append(
                "Biggest categories: "
                + ", ".join(f"{r['key']} {r['pct']:.0f}%" for r in rows)
                + "."
            )
        if wants_explain or category:
            series = call("get_monthly_series", {"category": category} if category else {})
            points = series.get("points", [])
            if points:
                peak = max(points, key=lambda p: p["tco2e"])
                lines.append(
                    f"Peak month for {category or 'the company'}: {peak['month']} "
                    f"at {peak['tco2e']:,.1f} tCO2e."
                )

    lines.append(
        "Note: running in offline mode — no Gemini API key configured, so responses come "
        "from the deterministic engine rather than a language model."
    )

    return {
        "answer": "\n".join(lines),
        "tool_calls": trace,
        "grounded": True,
        "mode": "offline",
        "model": None,
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def chat(db: Session, company_id: int, message: str) -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        return _offline_chat(db, company_id, message)
    try:
        return _gemini_chat(db, company_id, message)
    except Exception as exc:  # noqa: BLE001 - degrade instead of 500
        fallback = _offline_chat(db, company_id, message)
        fallback["answer"] = (
            f"Gemini call failed ({type(exc).__name__}: {exc}). "
            "Falling back to the deterministic engine.\n\n" + fallback["answer"]
        )
        return fallback
