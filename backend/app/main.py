"""CarbonPilot API — application entry point.

Run:  python -m uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app import __version__
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.routers import actions, agent, dashboard, ingest, scenarios

logger = logging.getLogger("carbonpilot")

# Built static export of the Next.js UI, served in single-port demo mode.
_UI_ENV = os.environ.get("CARBONPILOT_UI_DIR")
UI_DIR = Path(_UI_ENV).resolve() if _UI_ENV else Path(__file__).resolve().parents[2] / "frontend" / "out"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        from app.models import Company
        from app.seed import seed_demo

        if db.scalar(select(Company.id).limit(1)) is None:
            logger.info("Empty database — loading the synthetic demo dataset")
            seed_demo(db)
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "AI Carbon Decision Engine. The LLM interprets data and explains results; "
        "every carbon number comes from the deterministic calculation engine."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(ingest.router)
app.include_router(scenarios.router)
app.include_router(actions.router)
app.include_router(agent.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "llm_enabled": settings.llm_enabled,
        "llm_model": settings.gemini_model if settings.llm_enabled else None,
        "database": settings.database_url.split("://", 1)[0],
        "ui_served": UI_DIR.exists(),
    }


# --------------------------------------------------------------------------- #
# Single-port demo mode
#
# `cd frontend && npm run build` writes a static export to frontend/out. When it
# is present we serve it from this same process, so presenting needs one command
# and one port — no Node, no second terminal, no CORS.
# --------------------------------------------------------------------------- #
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
else:

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": "/api/health",
            "ui": "Not built. Run `cd frontend && npm install && npm run build`, then restart.",
        }
