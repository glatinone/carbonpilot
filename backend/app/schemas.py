"""Pydantic request/response contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Effort = Literal["low", "medium", "high"]


# --------------------------------------------------------------------------- #
# Companies
# --------------------------------------------------------------------------- #

class CompanyOut(BaseModel):
    id: int
    name: str
    region: str

    model_config = {"from_attributes": True}


class CompanyCreate(BaseModel):
    name: str
    region: str = "WORLD"


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #

class ColumnMapping(BaseModel):
    column: str
    activity_type: str
    category: str
    unit: str
    scope: int
    confidence: float
    rationale: str
    alternatives: list[str] = Field(default_factory=list)


class MappingPreview(BaseModel):
    filename: str
    columns: list[str]
    suggested: list[ColumnMapping]
    sample_rows: list[dict[str, Any]]
    ambiguous: list[str]


class IngestRequest(BaseModel):
    csv_text: str
    column_map: dict[str, str] | None = Field(
        default=None,
        description="Override: source column name -> canonical activity_type",
    )
    company_id: int = 1


class IngestResult(BaseModel):
    activities_created: int
    rows_skipped: int
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    mapping: list[ColumnMapping] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Dashboard / insights
# --------------------------------------------------------------------------- #

class BaselineOut(BaseModel):
    total_tco2e: float
    total_cost_usd: float
    avg_monthly_tco2e: float | None = None
    activity_count: int
    month_count: int | None = None
    scope_split: dict[str, Any] = Field(default_factory=dict)
    period: dict[str, str] | None = None
    incomplete: bool = False


class BreakdownRow(BaseModel):
    key: str
    tco2e: float
    cost_usd: float
    pct: float


class SeriesPoint(BaseModel):
    month: str
    tco2e: float
    cost_usd: float


class AnomalyOut(BaseModel):
    month: str
    activity_type: str
    value_tco2e: float
    baseline_tco2e: float
    delta_tco2e: float
    change_pct: float
    z_score: float
    direction: str
    severity: str


class DriverOut(BaseModel):
    driver: str
    description: str
    baseline: float
    observed: float
    ratio: float


class InsightOut(BaseModel):
    headline: str
    detail: str
    activity_type: str
    month: str
    carbon_impact_t: float
    cost_impact_usd: float
    confidence_pct: float
    evidence: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #

class InterventionIn(BaseModel):
    activity_type: str
    reduction_pct: float = Field(ge=0, le=100)
    cost_delta_pct: float = 0.0


class ScenarioRequest(BaseModel):
    interventions: list[InterventionIn]
    label: str | None = None
    save: bool = False


class ConstraintRequest(BaseModel):
    min_carbon_reduction_pct: float = Field(default=10.0, ge=0, le=100)
    max_cost_increase_usd: float = 0.0
    max_interventions: int = Field(default=4, ge=1, le=6)
    limit: int = Field(default=5, ge=1, le=20)


# --------------------------------------------------------------------------- #
# Recommendations + actions
# --------------------------------------------------------------------------- #

class RecommendationOut(BaseModel):
    id: int
    title: str
    description: str
    activity_type: str
    carbon_impact_t: float
    cost_impact_usd: float
    effort: Effort
    confidence_pct: float
    score: float
    status: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ActionCreate(BaseModel):
    recommendation_id: int | None = None
    owner: str = "Unassigned"
    task: str | None = None


class ActionOut(BaseModel):
    id: int
    owner: str
    task: str
    expected_carbon_t: float
    expected_cost_usd: float
    status: str

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #

class ChatRequest(BaseModel):
    message: str
    company_id: int = 1


class ToolCallTrace(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    grounded: bool = True
    mode: Literal["gemini", "offline"] = "gemini"
    model: str | None = None
