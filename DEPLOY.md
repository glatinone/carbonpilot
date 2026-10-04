# DEPLOY.md — how CarbonPilot gets in front of a judge

Read this before touching a hosting provider. The current architecture is not a
conventional frontend/backend split, and deploying it as one will produce a UI
with no data behind it.

## LIVE NOW

```
https://carbonpilot.212-2-251-42.sslip.io
```

One origin serves the UI **and** the API: real Let's Encrypt certificate, no cold
start, no CORS to configure, nothing to keep awake. The judge opens this one link.

```
Internet ──▶ Caddy                     212.2.251.42  host a0-research  (192.168.1.2)
             TLS-ALPN-01, Let's Encrypt
             carbonpilot.212-2-251-42.sslip.io
                     │
                     ▼  reverse_proxy 192.168.1.4:8010   (internal network)
             CarbonPilot                   212.2.250.84  host a0-content  (192.168.1.4)
             systemd unit `carbonpilot`
             uvicorn app.main:app --host 0.0.0.0 --port 8010
             serves /api/*  AND  frontend/out/  (ui_served: true)
             SQLite at backend/carbonpilot.db
```

`sslip.io` is why there is no domain to buy: `<anything>.<ip-with-dashes>.sslip.io`
resolves to that IP automatically, so Caddy can obtain a real certificate for a
name nobody registered.

### Why this beats the Vercel plan

The earlier plan split the UI (Vercel, HTTPS) from the API (a second host), which
requires CORS, a second deployment, and `NEXT_PUBLIC_API_URL` baked at build time.
Serving both from one origin deletes all three problems. **Vercel is now optional**
and, for judging, redundant — see "Vercel, if you still want it" below.

### Reproducing it

```bash
# 1. code to the app host (no git credentials needed for a private repo)
tar czf - --exclude='__pycache__' --exclude='.venv' --exclude='node_modules' \
    backend frontend/out | ssh <app-host> 'mkdir -p ~/carbonpilot && tar xzf - -C ~/carbonpilot'

# 2. deps (Debian needs this first: the stock python has no ensurepip)
sudo apt-get install -y python3-venv
cd ~/carbonpilot/backend && python3 -m venv .venv && ./.venv/bin/pip install -e .

# 3. run it as a service, not a background shell — background processes over SSH
#    die with the session, and `nohup ... &` still holds the SSH channel open
#    /etc/systemd/system/carbonpilot.service  → ExecStart:
#      <backend>/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8010
#      Environment=CARBONPILOT_UI_DIR=<repo>/frontend/out
sudo systemctl enable --now carbonpilot

# 4. proxy site block in Caddy on the host that owns public :443
#    carbonpilot.212-2-251-42.sslip.io { tls { issuer acme { disable_http_challenge } }
#                                        reverse_proxy 192.168.1.4:8010 }
docker exec mybrain-mcp-caddy-1 caddy validate --config /etc/caddy/Caddyfile
docker exec mybrain-mcp-caddy-1 caddy reload   --config /etc/caddy/Caddyfile
```

Bind to `0.0.0.0`, not `127.0.0.1`, because the proxy lives on a **different host**.
Public exposure does not follow from binding — this provider's firewall drops every
port except 22 and the one host that owns :443. A raw public port is not an option;
the proxy is the only door.

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

## The LLM key — the one thing to set by hand

Until a key is present the deployed service reports `llm_enabled: false`, which
means the agent answers from its deterministic router and **never calls Gemini**.
Set it on the server; the key must not travel through a chat, a commit, or a shell
history:

```bash
# on the app host — edit ~/carbonpilot/backend/.env and type the value in yourself
printf 'GEMINI_API_KEY=%s\n' '<paste-here-on-the-server>' > ~/carbonpilot/backend/.env
chmod 600 ~/carbonpilot/backend/.env
sudo systemctl restart carbonpilot
curl -s localhost:8010/api/health | grep -o '"llm_enabled":[a-z]*'   # expect true
```

`app/config.py` reads `backend/.env` (gitignored), and `GEMINI_API_KEY` wins over
`GOOGLE_API_KEY`. Add `CARBONPILOT_REQUIRE_LLM=true` to make the app **refuse to
boot** rather than quietly fall back to offline mode — worth it for a judged demo,
because the silent fallback is otherwise only discovered on stage.

## Vercel, if you still want it

Optional now, and redundant for judging. It buys a second public URL at the cost of
reintroducing CORS:

```
NEXT_PUBLIC_API_URL = https://carbonpilot.212-2-251-42.sslip.io
CORS_ORIGINS        = https://<your-vercel-app>.vercel.app   # on the VPS, then restart
```

Import the repository with **Root Directory** `frontend/`. `NEXT_PUBLIC_*` is baked
at build time, so a Vercel UI must be **rebuilt** when that URL changes — editing
the variable alone changes nothing. Do not edit `frontend/.env.production` for
this; a variable present in the Vercel environment wins over the committed empty
default.

## The offline path (practise this one)

```bash
cd frontend && npm run build          # writes out/
cd ../backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8008
# one URL serves both the UI and the API
```

## Warm it up before presenting

Open the deployed URL, ask the Ask-panel one question, and run one constraint
search a few minutes before you present. That confirms the key works and the
datastore is awake, and it is the difference between a demo and an apology.

## Risks, and what to do about each

| Risk | Why it bites | Mitigation |
|---|---|---|
| LLM key missing on the server | The agent silently answers offline and never calls Gemini, so the "AI" does nothing on stage | Set `backend/.env`, restart, **verify `llm_enabled: true`**; use `CARBONPILOT_REQUIRE_LLM=true` so the app refuses to boot instead of degrading quietly |
| Gemini key reaches the public | A public backend can be called by anyone; the key's quota is yours | Cap spend in the Google console; rotate the key if it was ever pasted into a chat |
| Backend down at judging | Every panel empty, and it reads as a broken product | It is a systemd unit with `Restart=on-failure` — check `systemctl is-active carbonpilot`; keep the offline path ready |
| Proxy edit does not take effect | The site is in the Caddyfile, yet the hostname gets no certificate and still points at the old upstream | A Docker **file** bind mount pins the inode it was created with, so replacing that file on the host silently detaches the mount while `docker inspect` still shows the right path. `docker restart <caddy-container>`, then confirm `docker exec <caddy> grep -c carbonpilot /etc/caddy/Caddyfile` is 1 |
| CORS misconfigured (only if you add Vercel) | UI loads, every call fails, console fills with CORS errors | Set `CORS_ORIGINS` to the exact origin (scheme included, no trailing slash) |
| Secret committed to the repo | It is public forever; rotating later does not un-publish it | `.env` is gitignored; only `NEXT_PUBLIC_API_URL` is tracked, in `frontend/.env.*` |
| Stale static build | A redeploy serves an old bundle after a code change | Rebuild `frontend/out` and re-ship it; `NEXT_PUBLIC_*` is baked at build time |

## Before you push

```bash
git ls-files | grep -iE '\.env$|secret|credential|\.pem$|\.key$'   # expect: nothing sensitive
cd backend  && ./.venv/Scripts/python.exe -m pytest -q             # expect: green
cd ../frontend && npx tsc --noEmit                                 # expect: exit 0
```

The demo's own smoke test is `backend/scripts/preflight.py` — run it last, it
exercises every route, the constraint search and the agent in one command.
