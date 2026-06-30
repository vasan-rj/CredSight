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

// ── Path-to-Bankability (D1) ─────────────────────────────────────────────────

export interface PathStep {
  feature: string;
  plain_label: string;
  marginal_delta: number;  // composite pts gained (always > 0)
  timeframe_days: number;
}

export interface Pathway {
  app_id: string;
  basis: string;
  current_composite: number;
  target_band: string;
  projected_composite: number;
  projected_band: string;
  reachable: boolean;
  steps: PathStep[];
  disclaimer: string;
}

// ── Learning Loop (D2) ───────────────────────────────────────────────────────

export interface LearningSummary {
  total_decisions: number;
  overrides_up: number;
  overrides_down: number;
  segment_count: number;
  window_days: number;
}

export interface ModelVersion {
  version: string;
  changed: string;
  approved_by: string;
  ts: string;
  rec_id: string;
}

export interface RecalRecommendation {
  id: string;
  segment: string;
  pattern: string;
  suggestion: string;
  evidence_count: number;
  status: string;
}

// ── Needs assessment + product catalogue (D5) ───────────────────────────────

export interface NeedsAssessment {
  app_id: string;
  need_type: "working_capital" | "seasonal" | "capex" | "trade_finance";
  headline: string;
  estimated_amount: number;
  urgency: "immediate" | "medium_term" | "planning";
  evidence: string[];
  gst_only: boolean;
  consent_to_unlock: string[];
}

export interface ProductMatch {
  product_id: string;
  name: string;
  tagline: string;
  description: string;
  amount_estimate: number;
  tenor_range: [number, number];
  indicative_rate: number;
  key_features: string[];
  fit_reason: string;
  data_needed: string[];
  score_required: boolean;
  score_band_ok: boolean;
}

// Upload ingestion
export interface UploadPreview {
  sources_found: string[];
  missing_sources: string[];
  months_bank: number;
  months_gst: number;
  upi_txn_count: number;
  turnover_estimate: number | null;
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
  pathway?: Pathway | null;
  needs?: NeedsAssessment | null;
  product_matches?: ProductMatch[] | null;
  decision: { decision: string; reason: string; underwriter: string } | null;
}
