# DEPLOY.md — how CarbonPilot gets in front of a judge

Read this before touching a hosting provider. The current architecture is not a
conventional frontend/backend split, and deploying it as one will produce a UI
with no data behind it.

## What the code actually is

```
frontend/  Next.js 15, output: "export"  → `npm run build` writes frontend/out/
backend/   FastAPI + SQLite, serves /api/* AND (optionally) the built UI
```

`next.config.mjs` sets `output: "export"` and `trailingSlash: true` on purpose:
the exported UI is a folder of static files that FastAPI can serve itself. That
gives a **single-process demo** — one port, one command, no Node on the
presenting machine once the UI is built.

The consequence that matters:

> **Vercel cannot run the backend.** It is a Python process with a database and a
> Gemini key. Vercel hosting the UI alone gives you a page whose every panel is
> empty. This is the failure mode to avoid, and it looks like a broken product
> rather than a misconfiguration.

`NEXT_PUBLIC_API_URL` decides where the browser sends API calls:

| Build | Value | Meaning |
|---|---|---|
| `npm run dev` | `http://127.0.0.1:8008` | UI on :3000, API on :8008, absolute URL |
| `npm run build` | *(empty)* | Same origin — FastAPI serves the UI, no CORS |

Neither file contains a secret, and neither should ever: anything prefixed
`NEXT_PUBLIC_` is compiled into the public bundle.

## Recommended topology — C+: three targets, one codebase

```
┌──────────────────────────┐        ┌───────────────────────────────┐
│ Vercel                   │        │ VPS (persistent)              │
│ frontend/out — static UI │───────▶│ FastAPI /api/* + SQLite       │
│ NEXT_PUBLIC_API_URL =    │  CORS  │ GEMINI_API_KEY lives here     │
│   https://api.<host>     │        │ never sleeps, no cold start   │
└──────────────────────────┘        └───────────────────────────────┘

plus, on the laptop:
  the single-process build (FastAPI serving out/ on one port) for the
  offline presentation path if venue wifi fails
```

Why all three:
- **Vercel** gives the public URL that goes on the hackathon submission form.
- **The VPS** removes the two worst demo risks: a free-tier backend that sleeps
  (~30s cold start) and a backend that is simply down when judging happens.
- **The local single-process build** is the fallback that still works with no
  network at all. Practise this path, not just the Vercel one.

## Steps

### 1. Backend on the VPS

```bash
# on the VPS, in its own directory and its own port — do not disturb other services
cd /srv/carbonpilot/backend
python3 -m venv .venv && ./.venv/bin/pip install -e .
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Put a reverse proxy in front for TLS (Caddy is one line; nginx + certbot also
fine). Then set, in the backend's environment — **not in any committed file**:

```
GEMINI_API_KEY=<set on the server only>
CORS_ORIGINS=https://<your-vercel-app>.vercel.app
```

Restrict the host firewall so only 80/443 are public; keep the API port bound to
127.0.0.1 and let the proxy reach it.

### 2. UI on Vercel

Import the repository, set **Root Directory** to `frontend/`, and add the
environment variable:

```
NEXT_PUBLIC_API_URL = https://api.<your-host>
```

Do not edit `.env.production` for this. A variable already present in the
environment wins over the file, so the committed empty default stays correct for
the single-process build.

### 3. The offline path (practise this one)

```bash
cd frontend && npm run build          # writes out/
cd ../backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8008
# one URL serves both the UI and the API
```

### 4. Warm it up before presenting

Open the deployed URL, ask the Ask-panel one question, and run one constraint
search a few minutes before you present. That confirms the key works and the
datastore is awake, and it is the difference between a demo and an apology.

## Risks, and what to do about each

| Risk | Why it bites | Mitigation |
|---|---|---|
| Gemini key reaches the public | A public backend can be called by anyone; the key's quota is yours | Rate-limit at the proxy; cap spend in the Google console; rotate the key if it was ever pasted into a chat |
| Backend asleep or down at judging | Every panel empty, and it reads as a broken product | VPS instead of a free tier; warm-up request first; keep the offline path ready |
| CORS misconfigured | UI loads, every call fails, console fills with CORS errors | Set `CORS_ORIGINS` to the exact Vercel origin (scheme included, no trailing slash) |
| Secret committed to the repo | It is public forever; rotating later does not un-publish it | `.env` is gitignored; only `NEXT_PUBLIC_API_URL` is tracked, in `frontend/.env.*` |
| Stale static build | Vercel serves an old bundle after a code change | `NEXT_PUBLIC_*` is baked at build time — redeploy after changing it, don't just edit the variable |

## Before you push

```bash
git ls-files | grep -iE '\.env$|secret|credential|\.pem$|\.key$'   # expect: nothing sensitive
cd backend  && ./.venv/Scripts/python.exe -m pytest -q             # expect: green
cd ../frontend && npx tsc --noEmit                                 # expect: exit 0
```

The demo's own smoke test is `backend/scripts/preflight.py` — run it last, it
exercises every route, the constraint search and the agent in one command.
