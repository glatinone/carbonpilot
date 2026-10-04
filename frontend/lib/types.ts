export type Baseline = {
  total_tco2e: number;
  total_cost_usd: number;
  avg_monthly_tco2e?: number;
  activity_count: number;
  month_count?: number;
  scope_split: Record<string, { tco2e: number; pct: number }>;
  period?: { start: string; end: string };
  incomplete: boolean;
};

export type BreakdownRow = { key: string; tco2e: number; cost_usd: number; pct: number };
export type SeriesPoint = { month: string; tco2e: number; cost_usd: number };

export type Anomaly = {
  month: string;
  activity_type: string;
  value_tco2e: number;
  baseline_tco2e: number;
  delta_tco2e: number;
  change_pct: number;
  z_score: number;
  direction: "spike" | "drop";
  severity: string;
};

export type Insight = {
  headline: string;
  detail: string;
  activity_type: string;
  month: string;
  carbon_impact_t: number;
  cost_impact_usd: number;
  confidence_pct: number;
  evidence: Record<string, unknown>;
};

export type RecommendationCalculation = {
  activity_value: number;
  activity_unit: string;
  factor_value: number | null;
  factor_source: string | null;
  factor_year: number | null;
  factor_uncertainty_pct: number | null;
  factor_count: number;
  result_tco2e: number;
};

/**
 * The comparison against the recommendation ranked immediately below this one.
 *
 * Sign conventions, set by the engine and relied on by the renderer:
 *   carbon_delta_t      positive = this action saves more carbon
 *   cost_delta_usd      negative = this action is financially better
 *   effort_delta        negative = this action is easier to ship
 */
export type RecommendationTradeoff = {
  vs_title: string;
  vs_rank: number;
  carbon_delta_t: number;
  cost_delta_usd: number;
  effort_delta: number;
  confidence_delta_pct: number;
};

export type Recommendation = {
  id: number;
  title: string;
  description: string;
  activity_type: string;
  carbon_impact_t: number;
  cost_impact_usd: number;
  effort: "low" | "medium" | "high";
  confidence_pct: number;
  score: number;
  status: string;
  evidence: Record<string, unknown> & {
    calculation?: RecommendationCalculation;
    tradeoff?: RecommendationTradeoff;
  };
};

export type Dashboard = {
  company: { id: number; name: string; region: string };
  baseline: Baseline;
  trend_pct: number | null;
  breakdown: BreakdownRow[];
  breakdown_by_activity: BreakdownRow[];
  series: SeriesPoint[];
  anomalies: Anomaly[];
  insights: Insight[];
  recommendations: Recommendation[];
  opportunity_count: number;
  llm_enabled: boolean;
};

export type Intervention = {
  activity_type: string;
  title: string;
  reduction_pct: number;
  cost_delta_pct: number;
  effort: "low" | "medium" | "high";
  confidence_pct: number;
};

export type ScenarioResult = {
  label: string;
  baseline: { total_tco2e: number; total_cost_usd: number };
  projected: { total_tco2e: number; total_cost_usd: number };
  impact: {
    carbon_saving_tco2e: number;
    carbon_reduction_pct: number;
    cost_delta_usd: number;
    cost_direction: "saving" | "increase" | "neutral";
  };
  per_intervention: Array<Record<string, unknown>>;
  assumptions: string[];
  is_estimate: boolean;
};

export type ConstraintScenario = {
  label: string;
  interventions: Array<{ activity_type: string; title: string; reduction_pct: number; effort: string }>;
  carbon_reduction_pct: number;
  carbon_saving_tco2e: number;
  cost_delta_usd: number;
  projected_tco2e: number;
  effort: string;
  confidence_pct: number;
  feasible: boolean;
};

export type ConstraintSearch = {
  constraints: {
    min_carbon_reduction_pct: number;
    max_cost_increase_usd: number;
    max_interventions?: number;
  };
  scenarios_evaluated: number;
  feasible: ConstraintScenario[];
  infeasible: ConstraintScenario[];
  recommended: ConstraintScenario | null;
  message: string;
};

export type ToolCallTrace = { tool: string; args: Record<string, unknown>; summary: string };

export type ChatResponse = {
  answer: string;
  tool_calls: ToolCallTrace[];
  grounded: boolean;
  mode: "gemini" | "offline";
  model: string | null;
};

export type ActionItem = {
  id: number;
  owner: string;
  task: string;
  expected_carbon_t: number;
  expected_cost_usd: number;
  status: string;
};

export type ColumnMapping = {
  column: string;
  activity_type: string;
  category: string;
  unit: string;
  scope: number;
  confidence: number;
  rationale: string;
  alternatives: string[];
};

export type MappingPreview = {
  filename: string;
  shape: "long" | "wide";
  columns: string[];
  suggested: ColumnMapping[];
  sample_rows: Array<Record<string, string>>;
  ambiguous: string[];
};

export type IngestResult = {
  shape: string;
  activities_created: number;
  rows_skipped: number;
  skipped: Array<Record<string, unknown>>;
  mapping: Record<string, string>;
};

/**
 * Grid benchmarks are a comparison layer, not the inventory factor library.
 * `basis` travels with every payload on purpose: Ember publishes full-lifecycle
 * CO2e intensity, which is NOT interchangeable with the generation-boundary
 * factor a location-based Scope 2 figure must use. The UI is expected to say so.
 */
export type JapacGridRow = {
  iso3: string;
  country: string;
  intensity: number;
  year: number;
  rank: number;
  shares_pct: Record<string, number | null>;
  delta_pct_vs_home: number;
  counterfactual_tco2e: number;
  counterfactual_delta_tco2e: number;
};

export type JapacBenchmark = {
  basis: string;
  unit: string;
  source: string;
  retrieved_via: string;
  licence: string;
  boundary_note: string;
  home: {
    iso3: string;
    country: string;
    intensity: number;
    year: number;
    rank: number;
    of: number;
    shares_pct: Record<string, number | null>;
  };
  measured: { electricity_kwh: number; tco2e: number };
  countries: JapacGridRow[];
};
