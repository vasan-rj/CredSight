// Mirrors the backend scoring/governance contracts (src/credsight/scoring/schema.py,
// governance/audit.py). Keep in sync — these are what the API returns.

export type Dimension =
  | "cash_flow_health"
  | "gst_turnover_signal"
  | "banking_discipline"
  | "business_vintage_stability"
  | "obligation_load_formality";

export interface ShapDriver {
  feature: string;
  value: number;
  shap_value: number;
  direction: "positive" | "negative";
}

export interface ScoreResult {
  app_id: string;
  model_version: string;
  dimensions: Record<Dimension, number>; // each 0-100
  composite: number; // 300-900
  confidence: number; // [0,1]
  shap: ShapDriver[];
}

export interface Recommendation {
  app_id: string;
  eligible: boolean;
  product: string;
  amount: number;
  indicative_rate: number;
  tenor_months: number;
  band_floor: number;
  out_of_policy: boolean;
  policy_clause_refs: string[];
}

export interface HITLRequest {
  app_id: string;
  reasons: string[];
  recommendation: Recommendation;
  score: ScoreResult;
  explanation: string;
}

export interface AuditEvent {
  app_id: string;
  ts: string;
  event_type: string;
  actor: string;
  detail: Record<string, unknown>;
  consent_ref?: string | null;
  model_version?: string | null;
}

export interface MsmeSummary {
  app_id: string;
  name: string;
  sector: string;
  composite: number;
  confidence: number;
  status: "pending_human" | "approved" | "rejected" | "needs_info";
}

// Demo applicants the orchestrator can run (GET /api/catalog).
export interface CatalogItem {
  app_id: string;
  name: string;
  archetype: "thin_file" | "strong" | "stressed" | "fraud";
  seed: number;
  sector: string;
}

// Unified result from POST /api/orchestrator/run and /resume — carries the full score
// whether the run paused at the HITL gate or auto-decided.
export interface RunResult {
  app_id: string;
  status: "pending_human" | "approved" | "rejected" | "needs_info";
  paused: boolean;
  reasons: string[];
  score: ScoreResult;
  recommendation: Recommendation;
  explanation: string;
  decision: { decision: string; reason: string; underwriter: string } | null;
}
