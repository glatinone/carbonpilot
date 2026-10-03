import type {
  ActionItem,
  ChatResponse,
  ConstraintSearch,
  Dashboard,
  Intervention,
  Recommendation,
  ScenarioResult,
} from "./types";

// Empty string means "same origin as the page" — used by the static-export
// build, where the FastAPI backend serves the UI itself.
const RAW = (process.env.NEXT_PUBLIC_API_URL ?? "").trim();
export const API_URL = RAW;

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(`${response.status} ${detail}`, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; llm_enabled: boolean; llm_model: string | null }>("/api/health"),

  dashboard: (companyId = 1) => request<Dashboard>(`/api/dashboard?company_id=${companyId}`),

  interventions: (companyId = 1) =>
    request<{ count: number; interventions: Intervention[] }>(
      `/api/interventions?company_id=${companyId}`,
    ),

  runScenario: (
    interventions: Array<{ activity_type: string; reduction_pct: number; cost_delta_pct?: number }>,
    companyId = 1,
    label?: string,
  ) =>
    request<ScenarioResult>(`/api/scenarios/run?company_id=${companyId}`, {
      method: "POST",
      body: JSON.stringify({ interventions, label, save: false }),
    }),

  constraints: (
    payload: { min_carbon_reduction_pct: number; max_cost_increase_usd: number; max_interventions?: number },
    companyId = 1,
  ) =>
    request<ConstraintSearch>(`/api/scenarios/constraints?company_id=${companyId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  recommendations: (companyId = 1) =>
    request<{ count: number; recommendations: Recommendation[] }>(
      `/api/recommendations?company_id=${companyId}`,
    ),

  actions: (companyId = 1) =>
    request<{
      count: number;
      totals: { expected_carbon_t: number; expected_cost_usd: number };
      note: string;
      actions: ActionItem[];
    }>(`/api/actions?company_id=${companyId}`),

  createAction: (recommendationId: number, owner: string, companyId = 1) =>
    request<ActionItem>(`/api/actions?company_id=${companyId}`, {
      method: "POST",
      body: JSON.stringify({ recommendation_id: recommendationId, owner }),
    }),

  updateAction: (actionId: number, status: string, companyId = 1) =>
    request<{ id: number; status: string }>(
      `/api/actions/${actionId}?status=${status}&company_id=${companyId}`,
      { method: "PATCH" },
    ),

  chat: (message: string, companyId = 1) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, company_id: companyId }),
    }),
};

export { ApiError };
