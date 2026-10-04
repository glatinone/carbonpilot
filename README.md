# CarbonPilot

**An AI carbon decision engine.**

> Companies can already measure their carbon footprint. CarbonPilot answers the
> next question: **what should we do about it?**

`Measure → Diagnose → Simulate → Act` · *and compare your grid against the region*

**Live demo:** <https://carbonpilot.212-2-251-42.sslip.io> — the UI and the API on one
origin (FastAPI serves both), so there is no second deployment and no CORS to configure.

```
backend/    FastAPI + SQLAlchemy — deterministic engines + Gemini tool-calling agent
frontend/   Next.js + Tailwind + Recharts — six screens, English/Indonesian, static export
```

> [`STATUS.md`](STATUS.md) — what is true right now · [`DEMO.md`](DEMO.md) — the 3-minute demo
> script · [`DEPLOY.md`](DEPLOY.md) — deployment topology and its risks · [`DESIGN.md`](DESIGN.md) —
> the design system the UI is built from

---

## The idea in one paragraph

Sustainability teams have the data (electricity, cloud, travel, fleet, procurement) but it is
scattered across CSVs, invoices and ERP exports. Even after it is aggregated into a single number
— *"11,208 tCO₂e/year"* — the question management actually asks is unanswered: **which action
should we take next, what will it cost, and how confident are we?**

CarbonPilot measures the footprint, uses an LLM agent to investigate what moved and why, simulates
interventions, and ranks the resulting actions by **carbon impact × financial impact ×
implementation effort**. Every number is traceable to raw activity data and a cited emission
factor.

## The one architectural rule

> **The LLM never produces a carbon number.**

```
                    ┌──────────────────────────┐
   user question ─► │  Gemini agent            │  interprets, selects tools,
                    │  (reasoning + interface) │  explains results
                    └────────────┬─────────────┘
                                 │ tool calls
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
     │ Data tools   │   │ Carbon engine│   │ Scenario     │
     │ (mapping,    │   │ activity ×   │   │ engine       │
     │  breakdown)  │   │ factor       │   │ + constraints│
     └──────────────┘   └──────────────┘   └──────────────┘
                                 │
                                 ▼
                        source of truth (kgCO₂e)
```

The agent's failure mode is therefore *"I could not find that"*, never *"here is a plausible
number"*. `backend/app/engine/` is pure, deterministic and unit-tested; `backend/app/agent/` only
orchestrates it.

## Four layers

| Layer | Question | Where |
|---|---|---|
| **Measure** | How much carbon? | `engine/calculator.py` — activity × emission factor |
| **Diagnose** | Why did it change? | `engine/anomaly.py` — robust median/MAD z-score + attributed drivers |
| **Simulate** | What if we change it? | `engine/scenario.py` — interventions + constraint search |
| **Act** | What should we do? | `engine/recommender.py` — carbon × cost × effort, confidence-weighted |

### Gen AI does four real jobs

1. **Data understanding** — maps messy headers (`electricity_consumed`, `fuel_litre`) onto
   canonical activity types, scopes and units (`engine/mapping.py` is the deterministic half the
   agent cites).
2. **Investigation** — chains tool calls (`detect_anomalies` → `explain_anomaly` →
   `compare_month`) before it is allowed to answer "why".
3. **Scenario orchestration** — turns *"cut 15% without raising cost"* into a constraint search
   over the intervention catalogue.
4. **Recommendation** — reports what, why, how much, the assumption, and the next action.

## Grid benchmarks — where the answer depends on location

`/japac` prices the company's **measured** electricity against every grid in the region, from the
Ember Yearly Electricity Data (20 grids, CC BY 4.0), each row carrying its own data year and
generation mix so the intensity has an explanation attached.

The demo company draws 4,304,333 kWh. On Indonesia's grid that is 3,036 tCO₂e — **rank 19 of 20**,
coal 69%. The same consumption on New Zealand's grid would be 399 tCO₂e. The difference is
location, not effort, and that turns *"how much do we emit"* into *"where does this change"*.

**Boundary discipline, because it matters here.** Ember publishes *full-lifecycle* CO₂e intensity;
the inventory's Scope 2 figure uses a *generation-boundary* curated factor. The two are not
interchangeable, so the benchmark ships as its own document and is never merged into the factor
library — and `measured.tco2e` is computed from the stored inventory calculation, never from
Ember. The visible consequence: the same grid reads **705.3** in the benchmark and **712** in the
inventory, and both are labelled rather than quietly averaged. `preflight` fails if the payload
ever loses its basis.

## Two languages, no added dependency

English and Indonesian, switched from the sidebar. The app is a static export, so there is no
server to route by locale and a client provider is the only architecture that fits — which also
means no new package in the build. Dictionaries are flat key maps with resolution order
*locale → English → the key*, so an incomplete translation degrades to a readable language rather
than showing a raw identifier.

Long sentences are stored whole as templates with `{placeholders}`, and the emphasis is applied
when substituting — because word order differs per language, and concatenating translated
fragments cannot survive that.

UI chrome is fully bilingual. Text the **engine and model** generate — recommendation titles, the
constraint-search message, the agent's answers — stays English; translating those is a backend
change, not a UI one. Stated here rather than hidden.

## Quick start

Two terminals.

**Backend**

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
cp .env.example .env                    # add GEMINI_API_KEY (optional — see below)
.venv/Scripts/python -m app.seed --csv ./demo_data --seed-db
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8008
```

- API docs: http://localhost:8008/docs
- Without a Gemini key the app still runs end to end: the agent falls back to a deterministic
  router and the UI labels the response `Deterministic engine` instead of `Gemini`.

**Frontend**

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```

> If your Gemini deployment uses namespaced model ids (e.g. a gateway that exposes
> `google/gemini-2.5-flash`), set `GEMINI_MODEL` in `backend/.env` to the exact id. A `404
> not_found` from the model means the id is wrong, not that the key is.

## Demo dataset

`python -m app.seed --csv ./demo_data --seed-db` writes five upload-ready CSVs and loads a
coherent 12-month history for a fictional Indonesian digital-services group
(**PT Nusantara Digital**, grid region `ID`):

| Stream | Annual | Notes |
|---|---:|---|
| Procurement | ~5,300 t | largest share (spend-based, Scope 3) |
| Electricity + gas | ~3,200 t | Scope 2, Indonesian grid factor 0.712 kgCO₂e/kWh |
| Fleet | ~1,100 t | Scope 1 diesel + petrol |
| Business travel | ~1,000 t | flights, hotels, rail |
| Cloud | ~270 t | small share of carbon (2.4%), ~33% of tracked spend |
| Waste + water | ~140 t | Scope 3 |

**Two anomalies are planted on purpose**, so the AI has something real to find:

- **May 2026 — cloud compute +165%**, driven by a weekend workload
  (`weekend_share` 0.15 → 0.60, i.e. ~4× the baseline). This is the demo hero.
- **September 2026 — diesel +58%**, a distribution surge.

Cloud being a small slice of *carbon* while a large slice of *cost* is realistic (Cloud Carbon
Footprint per-vCPU-hour intensities are small) and is itself a good talking point — the point of
the product is the decision, not the size of one bar.

## API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/dashboard` | hero metrics, breakdown, series, anomalies, insights, recommendations |
| `GET` | `/api/anomalies`, `/api/anomalies/explain` | detection + evidence trail |
| `GET` | `/api/interventions` | the intervention catalogue derived from this company's data |
| `POST` | `/api/scenarios/run` | simulate explicit interventions |
| `POST` | `/api/scenarios/constraints` | *"reduce X% without increasing cost"* search |
| `GET`/`POST` | `/api/recommendations` | ranked actions |
| `GET`/`POST`/`PATCH` | `/api/actions` | owned, tracked action items |
| `GET` | `/api/actions/export` | the tracked plan as a Markdown or CSV document |
| `POST` | `/api/chat` | Gemini tool-calling agent (with tool-call trace) |
| `GET` | `/api/japac` | measured electricity priced against 20 JAPAC grids, with basis and licence |
| `POST` | `/api/ingest/preview`, `/api/ingest` | CSV upload: mapping preview then calculation |

## Tests

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q      # 101 tests
cd frontend && npm run typecheck
```

Tests assert **behaviour contracts**, not snapshots: `co2e == value × factor`, the spike is
detected despite inflating its own spread (the reason for MAD over standard deviation), a
projection plus its saving equals the baseline, and the constraint search only ever returns
scenarios that satisfy the constraints.

## Honest limitations (state these to judges)

- Emission factors are curated point estimates for prototype use; production would pull live
  factors from Climatiq or the issuing authority. Each factor carries an `uncertainty_pct`, which
  is propagated into the recommendation's **confidence** score rather than hidden. A Climatiq
  client ships (`app/engine/climatiq.py`, opt-in via `CLIMATIQ_API_KEY`) so the agent can
  corroborate a factor against the live published one and cite it — deliberately off the
  calculation path, so a rehearsed demo cannot move because a third party changed a number.
- Scenario maths is linear (`baseline × reduction%`), with no rebound effect or learning curve.
  The UI labels every projection **Estimated impact** and lists its assumptions.
- Scope 3 spend-based procurement is the crudest line in the model (60% uncertainty) — and it is
  the largest, which is exactly why the confidence column exists.

## Competitive honesty

Persefoni and Watershed already do carbon accounting, AI copilots, anomaly detection and scenario
planning. **Do not pitch "the first AI carbon platform."**

Pitch instead:

> *Existing platforms help companies measure and manage carbon. CarbonPilot focuses on the
> decision moment: which action should we take next, why, and what carbon and financial impact
> can we expect — with every estimate traceable to source data.*
