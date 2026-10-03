# CarbonPilot — Backend

FastAPI service for **CarbonPilot**, the AI Carbon Decision Engine.

`Measure → Diagnose → Simulate → Act`

## The one rule that matters

> **The LLM never produces a carbon number.**

Gemini interprets messy data, chooses which analytical tool to call, and explains
the result. Every kilogram of CO2e comes from the deterministic calculation
engine in `app/engine/`, which multiplies activity data by a cited emission
factor from `app/data/emission_factors.json`.

```
ACTIVITY DATA  ×  EMISSION FACTOR  =  kgCO2e        (app/engine/calculator.py)
```

## Layout

```
app/
  config.py          settings + secrets loading (.env)
  db.py              SQLAlchemy session / engine bootstrap
  models.py          Company, Activity, EmissionFactor, Calculation,
                     ScenarioRecord, Recommendation, ActionItem
  schemas.py         Pydantic request/response contracts
  seed.py            synthetic 12-month demo dataset (with deliberate anomalies)
  data/
    emission_factors.json   cited factor library (GHG Protocol scopes)
  engine/            deterministic core — no LLM, unit-tested
    factors.py       factor library lookup + region fallback
    mapping.py       messy column -> canonical activity type
    calculator.py    activity x factor, aggregation, period comparison
    anomaly.py       robust z-score (median/MAD) + driver attribution
    scenario.py      what-if simulation + constraint search
    recommender.py   carbon x cost x effort prioritisation
  agent/             Gen AI layer
    tools.py         tool schemas exposed to Gemini
    gemini_agent.py  tool-calling loop (+ deterministic offline fallback)
  routers/           HTTP surface
  tests/             engine tests
```

## Run it

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"

cp .env.example .env          # then paste your Gemini key
.venv/Scripts/python -m app.seed --csv ./demo_data --seed-db

.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

## Database

SQLite by default (`carbonpilot.db`). Point `DATABASE_URL` at Postgres/Supabase
for a shared instance — no code changes needed.
