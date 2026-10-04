# STATUS.md — CarbonPilot project state

**Last updated:** 2026-10-04
**Competition:** JAPAC AI hackathon (Google AI builder)
**Repo:** private, `glatinone/carbonpilot`
**Live:** `https://rakazo-civo.tail1b51ed.ts.net:8443`

This is the working status board. `README.md` is the pitch, `DEPLOY.md` is the
topology, `DESIGN.md` is the design system. This file is what is true *now*.

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
- No repeatable deploy script. Deployment is currently a manual copy of changed files
  plus `systemctl restart`; every future fix repeats it. A small `scripts/deploy.sh`
  reading host/key from the environment would remove that step.
- `llm_model_resolved` is `null` until the first chat call resolves the model. Correct
  but momentarily unhelpful in health output.
- Per-page tab titles are not set — every screen shows the same title.

**Deliberately not done**
- No new dependency for i18n. The app is a static export, so a client provider is the
  only architecture that fits; adding a package would have bought nothing.
