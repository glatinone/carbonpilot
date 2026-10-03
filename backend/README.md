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

.venv/Scripts/python -m uvicorn app.main:app --reload --port 8008
```

API docs: http://localhost:8008/docs

## Two correct ways to run the UI

The backend and UI can be wired together two ways. Pick one; do not mix them.

**(a) DEV — two processes, two ports.** Run the API on **8008**:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8008
```

and the UI on **3000** with `npm run dev`:

```bash
cd ../frontend && npm run dev
```

`frontend/.env.development` points the UI at `http://127.0.0.1:8008`, so every
`/api` call reaches this backend. Use this while editing code.

**(b) SINGLE-PORT DEMO — one process, one port.** Build the static export once,
then let FastAPI serve it on the same port as the API:

```bash
cd ../frontend && npm run build        # writes frontend/out
cd ../backend && .venv/Scripts/python -m uvicorn app.main:app --port 8008
```

FastAPI serves `frontend/out` at `/` and the API at `/api`, so the whole demo is
one process on one port (`http://localhost:8008`) — no CORS, no second terminal.

> **`next start` is NOT supported here.** `frontend/next.config.mjs` sets
> `output: "export"`, and the production build bakes an empty
> `NEXT_PUBLIC_API_URL` (same-origin only). Serving that build from the Next.js
> server therefore makes every `/api` call 404 — nothing proxies it to FastAPI.
> Serve the static export from FastAPI (option b) instead.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

## Database

SQLite by default (`carbonpilot.db`). Point `DATABASE_URL` at Postgres/Supabase
for a shared instance — no code changes needed.
