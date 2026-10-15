# STATUS.md — CarbonPilot project state

**Last updated:** 2026-10-15
**Competition:** JAPAC AI hackathon (Google AI builder)
**Repo:** public, `glatinone/carbonpilot`
**Live:** `https://rakazo-civo.tail1b51ed.ts.net:8443`

This is the working status board. `README.md` is the pitch, `DEPLOY.md` is the
topology, `DESIGN.md` is the design system. This file is what is true *now*.

---

## 2026-10-15 — YOLO round: what was done

One parallel batch + parent work. Final state **verified live** at the URL above:
113 backend tests, `tsc` exit 0, production build 7 routes, deployed, smoke-tested
on the public funnel.

| Item | What landed | Proof |
|---|---|---|
| Persistent service | systemd unit `enabled` + `Restart=always` + auto-start | unit template, `systemctl is-enabled`, live health |
| Public repo | `glatinone/carbonpilot` visibility public | github page |
| Bilingual constraint message | constraint-search result now per-locale (`message_key` + counts, additive) | pytest, live `sim.searchFeasible` |
| Per-page tab titles | 6 unique titles, static export | build, DOM check |
| `scripts/deploy.sh` | idempotent, double health check, rsync-fallback to scp | deploy run |
| **MAC curve** | 16-action marginal abatement cost curve — dot per action, X = cumulative t, Y = net $/t (symlog), effort = colour, full 16-chip legend, bilingual | pytest 105 → integrated; live render EN+ID |
| **Carbon pricing scenario** | one human number ($/t) → engine revalues footprint + re-ranks all 16 actions by net position, machine verdict sentence | 8 new tests; live: $100/t ⇒ $1,120,792/yr, order changed (nonzero deltas), monotone |

### MAC curve — design decisions

- **Dots, not bars.** Bars would smear a 1.9 t action against a 2,452 t one
  (~0.3 px); each item is a dot at the centre of the tonnes it adds, so all 16 read.
- **Y = symlog**, linear ±$300 and logarithmic beyond; **X = linear** cumulative
  tonnes (log would break the "must sum" property).
- Money is position against the zero line; effort is the only colour, reusing the
  matrix palette. Rank number inside the dot = card number; the 16-chip legend below
  makes every action readable without hover. `mac.*` keys added (12 per language).

### Carbon pricing — design decisions

- **Deterministic by construction**: baseline tonnes × price; each action's net
  position = its proven cost impact + tonnes × price. No LLM arithmetic anywhere.
- **Verdict is keyed** (`pricing.paysForItself` / `stillCosts` / `financialOnly` /
  `empty`), assembled from structured fields, so each language phrases it itself.
- UI: price input + presets ($0–$150) on the Actions page between the MAC curve and
  the ranked list; re-ranked table shows #, t, carbon value, net/yr, delta vs the
  cost-only rank.
- **Verified live** at both $50/t (annual carbon cost $560,396 on 11,208 t) and
  $100/t (order actually changed — nonzero deltas, net monotone, verdict valid).
  Endpoint: `POST /api/pricing/scenario`.
- File map (all new): `backend/app/engine/pricing.py` (engine),
  `backend/app/routers/pricing.py` (POST endpoint), `backend/app/tests/test_pricing.py`
  (8 tests), `frontend` `PricingPanel` + i18n (`pricing.*`, 23 keys/language; parity 339=339).

### Pitch-deck + video brief

`docs/brief-pitch-deck-video.md` is the new brief for building the pitch deck and
presentation video with Claude Opus 5.5 — anchor numbers, story arc, MAC + pricing
demo beats, language recommendation. See that file.

---

## Where it is deployed

A single FastAPI process serving both the API and the built UI (the project's
single-port mode), running as a `systemd` unit on a Civo VPS, exposed publicly
through a Tailscale Funnel. No inbound firewall port was opened — the host's UFW
policy is unchanged, and the tunnel is outbound.

```
service    carbonpilot.service      enabled (survives reboot) + active
bind       0.0.0.0:<port>           serves /, /api/*, and the static export
health     GET /api/health          llm_mode, llm_model_resolved, llm_last_error, ui_served
public     443 via Tailscale Funnel  real TLS, no domain required
```

**Operational gotcha worth not rediscovering.** The Gemini key is a *gateway* key
(`sk-ai-…`), not a Google AI Studio key. The google-genai SDK builds its endpoint
from the process environment, so an endpoint override that exists only in `.env` is
ignored, the key gets sent to Google, and every model call fails — while the agent
quietly answers from the deterministic router and `/api/health` still reports
`mode=gemini`. `app/config.py` now declares the field and `gemini_agent` exports it
before constructing the client, so one `.env` is enough. See the commit that fixed it.

---

## What is built

| Area | State |
|---|---|
| Measure / Diagnose / Simulate / Act | complete — deterministic engines, all unit-tested |
| Gemini tool-calling agent | complete, with tool-call trace shown in the UI |
| CSV ingest | complete — map first, calculate second, both preview tables in the UI |
| Action plan + export | complete — Markdown and CSV export of the tracked plan |
| **JAPAC grid benchmarks** | complete — 20 grids, new page, new endpoint |
| **English / Indonesian** | complete for all UI chrome, toggle in the sidebar |
| **Ledger design system** | complete — `DESIGN.md`, all six screens rebuilt |

Six screens: `/`, `/upload/`, `/insights/`, `/simulator/`, `/actions/`, `/japac/`.

### The headline finding

The demo company draws **4,304,333 kWh**. On Indonesia's grid that is **3,036 tCO₂e**
— rank **19 of 20** in the region, coal 69%. The same consumption on New Zealand's
grid would be **399 tCO₂e**. The difference is location, not effort.

---

## Verified, with the command that proved it

```
101 → 105 tests           cd backend && ./.venv/Scripts/python.exe -m pytest -q
typecheck                 cd frontend && npx tsc --noEmit          → exit 0
production build          cd frontend && npm run build             → 7 routes
deployment smoke test     ./.venv/Scripts/python.exe scripts/preflight.py --base-url <public URL>
                          → READY, 13 OK, 1 WARN (Climatiq is optional and unconfigured)
```

`preflight` is the presentation smoke test. It checks every route, the constraint
search, the upload mapping, the grid benchmarks, and the agent — and it now **fails**
if a configured key is not actually working. Before that check existed, a deployment
whose AI was dead passed preflight, because the deterministic router still returns
correct numbers and real tool calls.

### Numbers that must not drift

```
11,208 tCO2e / year      168 activity records        12 months
Scope 1/2/3              11.6% / 27.3% / 61.1%
Cloud                    271 t (2.4% of carbon) but 33% of tracked spend
Grid benchmark home      Indonesia 705.3 gCO2e/kWh, rank 19/20
```

---

## Submission package — 2026-10-06

All artifacts live in `submission/`; every one is generated by a script in
`submission/scripts/` (deck builder, one-pager, frame capture, audio mux).

| Artifact | File | Notes |
|---|---|---|
| Proposal deck — editable | `submission/CarbonPilot_submission_deck.pptx` | 12 slides, Ledger design, speaker notes per slide |
| Proposal deck — PDF | `submission/CarbonPilot_submission_deck.pdf` | Exported via PowerPoint; design fonts embedded |
| Submission one-pager | `submission/CarbonPilot_one_pager.pdf` | One letter page |
| Explainer video | `submission/explainer.mp4` | ~84 s, 1920×1080, English narration |
| Demo video | `submission/demo.mp4` | ~2:05, 1920×1080, live-app walkthrough |
| Narration + live captures | `submission/assets/` | TTS segments; 7 live screenshots 1920×1080 |

Verified 2026-10-06: deck PDF embeds Source Serif 4 / Inter / IBM Plex Mono (no font
substitution); one-pager is exactly one page; explainer 84.5 s with narration aligned;
demo 124.5 s ending with the live constraint-search result — “342 of 2,098 scenarios
satisfy both constraints”, −33.8% carbon, −$775K/yr — captured from the deployed
instance; both videos loudness-normalised (−16 LUFS).

Narration is TTS (Edge voices). To swap in a human take: re-record the same script
(copy lives in `submission/scripts/content.json`, arrays `explainer` / `demo`) as
`submission/assets/audio/n*.mp3` / `d*.mp3`, then re-run
`submission/scripts/build_audio.py explainer|demo`.

---

## Honest limitations (state these to judges)

- **Engine- and model-generated text is English only.** Recommendation titles, the
  constraint-search message, and the agent's answers come from the backend, so making
  them bilingual is a backend change (pass the locale, translate at the source), not a
  UI one. All UI chrome is bilingual.
- **The benchmark basis is not the inventory basis.** Ember publishes full-lifecycle
  CO₂e intensity; the inventory's Scope 2 figure uses a generation-boundary curated
  factor. The page states this and `measured.tco2e` is computed from the stored
  inventory calculation — the same grid reads 705.3 in the benchmark and 712 in the
  inventory, deliberately labelled rather than averaged.
- Emission factors are curated point estimates; Climatiq is wired up but unconfigured.
- Scenario maths is linear — no rebound effect, no learning curve.
- Scope 3 spend-based procurement carries ~60% uncertainty and is the largest line.

---

## Open items

**Decided — one URL, do not reopen**
- **The public address is final:** `https://rakazo-civo.tail1b51ed.ts.net:8443`, behind a
  Tailscale Funnel. A tidier `<ip>.sslip.io` hostname was built, verified working from
  outside, then **removed**: office DNS sinkholes `sslip.io`, so the name is unreachable
  from the owner's own machine even though it resolves elsewhere. A second address that
  breaks exactly where the demo happens is worse than none, so there is deliberately
  only one.
- Publish the repository when submitting (`gh repo edit glatinone/carbonpilot --visibility public`).

**Known gaps, no blocker**
- English-only backend text is down to recommendation *descriptions* and the agent's
  own answers. The constraint-search result is now bilingual (2026-10-15); the MAC
  curve and pricing labels are bilingual by construction. Titles/descriptions and
  chat stay English from the backend.
- `llm_model_resolved` is `null` until the first chat call resolves the model. Correct
  but momentarily unhelpful in health output.

**Deliberately not done**
- No new dependency for i18n. The app is a static export, so a client provider is the
  only architecture that fits; adding a package would have bought nothing.
