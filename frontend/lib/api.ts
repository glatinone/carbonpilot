import type {
  ActionItem,
  ChatResponse,
  ConstraintSearch,
  CourseCheck,
  Dashboard,
  IngestResult,
  Intervention,
  JapacBenchmark,
  MappingPreview,
  PricingScenario,
  Recommendation,
  ScenarioResult,
  SupplierBreakdown,
  Trajectory,
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

/**
 * Multipart upload. Deliberately sets no Content-Type: the browser has to set
 * it itself so the multipart boundary matches the encoded body.
 */
async function upload<T>(path: string, file: File, fields: Record<string, string> = {}): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  for (const [key, value] of Object.entries(fields)) body.append(key, value);

  const response = await fetch(`${API_URL}${path}`, { method: "POST", body, cache: "no-store" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const parsed = await response.json();
      detail = parsed?.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(`${response.status} ${detail}`, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; llm_enabled: boolean; llm_model: string | null }>("/api/health"),

  // Ingestion is a two-step round trip on purpose: map first so the operator
  // sees how each column was read, then import.
  ingestPreview: (file: File) => upload<MappingPreview>("/api/ingest/preview", file),

  ingest: (file: File, columnMap: Record<string, string> = {}, companyId = 1) =>
    upload<IngestResult>("/api/ingest", file, {
      company_id: String(companyId),
      column_map: JSON.stringify(columnMap),
    }),

  dashboard: (companyId = 1) => request<Dashboard>(`/api/dashboard?company_id=${companyId}`),

  // Grid benchmarks are a comparison layer, not the inventory factor library, so
  // the payload carries its own basis and licence and the UI is expected to show
  // them rather than silently reuse the numbers.
  japac: (companyId = 1) => request<JapacBenchmark>(`/api/japac?company_id=${companyId}`),

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

  pricingScenario: (priceUsdPerT: number, companyId = 1) =>
    request<PricingScenario>(`/api/pricing/scenario`, {
      method: "POST",
      body: JSON.stringify({ company_id: companyId, price_usd_per_t: priceUsdPerT }),
    }),

  trajectory: (
    payload: { target_reduction_pct: number; target_year: number; price_usd_per_t?: number },
    companyId = 1,
  ) =>
    request<Trajectory>(`/api/trajectory`, {
      method: "POST",
      body: JSON.stringify({ company_id: companyId, ...payload }),
    }),

  suppliers: (companyId = 1) =>
    request<SupplierBreakdown>(`/api/suppliers?company_id=${companyId}`),

  course: (companyId = 1) =>
    request<CourseCheck>(`/api/course?company_id=${companyId}`),

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

  // A browser download, not a JSON round trip: the response carries
  // Content-Disposition, so an anchor can point straight at it.
  exportActionsUrl: (fmt: "md" | "csv" = "md", companyId = 1) =>
    `${API_URL}/api/actions/export?fmt=${fmt}&company_id=${companyId}`,

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
