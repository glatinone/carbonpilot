"""Conversational endpoint — the primary UI surface."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent import gemini_agent, tools
from app.db import get_db
from app.models import Company
from app.schemas import ChatRequest

router = APIRouter(prefix="/api", tags=["agent"])


@router.get("/agent/tools")
def list_tools() -> dict:
    """The agent's tool surface — shown in the UI as the 'reasoning' panel."""
    return {
        "count": len(tools.TOOLS),
        "tools": [
            {"name": name, "description": spec["description"]}
            for name, spec in tools.TOOLS.items()
        ],
    }


@router.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> dict:
    if db.get(Company, payload.company_id) is None:
        raise HTTPException(status_code=404, detail=f"Company {payload.company_id} not found")
    return gemini_agent.chat(db, payload.company_id, payload.message)
