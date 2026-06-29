// Mock data so the UI runs standalone (USE_MOCK=true in api.ts) before the backend is up.

import type { AuditEvent, CatalogItem, LearningSummary, ModelVersion, RecalRecommendation, RunResult } from "./types";

export const CATALOG: CatalogItem[] = [
  { app_id: "APP-LAKSHMI-001", name: "Lakshmi Stores",       archetype: "thin_file", seed: 101, sector: "Kirana / retail" },
  { app_id: "MSME0002",        name: "Sri Auto Works",        archetype: "strong",    seed: 102, sector: "Micro-manufacturing" },
  { app_id: "MSME0005",        name: "Anand Tailors",         archetype: "stressed",  seed: 103, sector: "Services" },
  { app_id: "MSME0007",        name: "Deccan Traders",        archetype: "fraud",     seed: 104, sector: "Wholesale" },
  // Expanded catalog — thin-file
  { app_id: "MSME0201", name: "Priya Flower Vendor",  archetype: "thin_file", seed: 201, sector: "Street vendor / flowers" },
  { app_id: "MSME0202", name: "Ramesh Cobblers",      archetype: "thin_file", seed: 202, sector: "Repair services" },
  { app_id: "MSME0203", name: "Fatima Street Food",   archetype: "thin_file", seed: 203, sector: "Food & beverages" },
  { app_id: "MSME0204", name: "Suresh Pan Shop",      archetype: "thin_file", seed: 204, sector: "Kirana / retail" },
  { app_id: "MSME0205", name: "Gita Tailoring Unit",  archetype: "thin_file", seed: 205, sector: "Textile / apparel" },
  // Strong
  { app_id: "MSME0206", name: "Raj Pharma Retail",    archetype: "strong",    seed: 206, sector: "Healthcare" },
  { app_id: "MSME0207", name: "Meera IT Services",    archetype: "strong",    seed: 207, sector: "IT services" },
  { app_id: "MSME0208", name: "Kumar Auto Dealer",    archetype: "strong",    seed: 208, sector: "Auto repair / parts" },
  { app_id: "MSME0209", name: "Sathya Dairy Farm",    archetype: "strong",    seed: 209, sector: "Agriculture / dairy" },
  // Stressed
  { app_id: "MSME0210", name: "Mohan Restaurant",     archetype: "stressed",  seed: 210, sector: "Food & beverages" },
  { app_id: "MSME0211", name: "Kavitha Textiles",     archetype: "stressed",  seed: 211, sector: "Textile / apparel" },
  { app_id: "MSME0212", name: "Ravi Construction",    archetype: "stressed",  seed: 212, sector: "Construction" },
  { app_id: "MSME0213", name: "Sunita Handicrafts",   archetype: "stressed",  seed: 213, sector: "Handicrafts" },
  // Fraud
  { app_id: "MSME0214", name: "Vijay Used Goods",     archetype: "fraud",     seed: 214, sector: "Wholesale" },
  { app_id: "MSME0215", name: "Arjun Cash Wholesale", archetype: "fraud",     seed: 215, sector: "Wholesale" },
  { app_id: "MSME0216", name: "Nanda Import Agents",  archetype: "fraud",     seed: 216, sector: "Wholesale" },
];

// Strong archetype — composite 900, Strong band, no pathway needed.
// Amount 500k < threshold 600k → auto-approved (no HITL pause).
export const MOCK_RUN: RunResult = {
  app_id: "MSME0002",
  status: "approved",
  paused: false,
  reasons: [],
  explanation:
    "Key factors: gst filing punctuality (supports); inflow regularity (supports); " +
    "balance volatility (weakens).",
  score: {
    app_id: "MSME0002",
    model_version: "v0",
    composite: 900,
    confidence: 0.93,
    dimensions: {
      cash_flow_health: 86,
      gst_turnover_signal: 92,
      banking_discipline: 96,
      business_vintage_stability: 74,
      obligation_load_formality: 80,
    },
    shap: [
      { feature: "gst_filing_punctuality", value: 1.0, shap_value: 1.21, direction: "positive" },
      { feature: "inflow_regularity", value: 0.87, shap_value: 0.74, direction: "positive" },
      { feature: "gst_turnover_trend", value: 0.32, shap_value: 0.51, direction: "positive" },
      { feature: "balance_volatility_norm", value: 0.45, shap_value: -0.42, direction: "negative" },
      { feature: "emi_to_inflow_ratio", value: 0.12, shap_value: 0.2, direction: "positive" },
    ],
  },
  recommendation: {
    app_id: "MSME0002",
    eligible: true,
    product: "Working capital (unsecured)",
    amount: 500000,
    indicative_rate: 16.0,
    tenor_months: 36,
    band_floor: 750,
    out_of_policy: false,
    policy_clause_refs: [],
  },
  pathway: null,
  decision: null,
};

// Thin-file hero case (Lakshmi) — composite 600, 2 actionable steps, reachable → Strong.
// Values from smoke test: thin_file seed=104 → composite=600, reachable=True.
export const MOCK_RUN_LAKSHMI: RunResult = {
  app_id: "APP-LAKSHMI-001",
  status: "pending_human",
  paused: true,
  reasons: ["recommendation == refer", "confidence 0.61 < floor 0.70"],
  explanation:
    "Key factors: inflow regularity (weakens — limited banking history); " +
    "gst filing punctuality (weakens — 2 missed quarters); " +
    "balance volatility norm (weakens — high swings).",
  score: {
    app_id: "APP-LAKSHMI-001",
    model_version: "v0",
    composite: 600,
    confidence: 0.61,
    dimensions: {
      cash_flow_health: 48,
      gst_turnover_signal: 55,
      banking_discipline: 58,
      business_vintage_stability: 62,
      obligation_load_formality: 40,
    },
    shap: [
      { feature: "inflow_regularity", value: 0.38, shap_value: -0.62, direction: "negative" },
      { feature: "gst_filing_punctuality", value: 0.5, shap_value: -0.48, direction: "negative" },
      { feature: "balance_volatility_norm", value: 0.71, shap_value: -0.31, direction: "negative" },
      { feature: "gst_turnover_trend", value: 0.29, shap_value: 0.18, direction: "positive" },
      { feature: "epfo_formality_proxy", value: 0.0, shap_value: -0.12, direction: "negative" },
    ],
  },
  recommendation: {
    app_id: "APP-LAKSHMI-001",
    eligible: false,
    product: "Working capital (unsecured)",
    amount: 0,
    indicative_rate: 0,
    tenor_months: 0,
    band_floor: 600,
    out_of_policy: true,
    policy_clause_refs: ["RBI-MSME-2024-§3.1"],
  },
  pathway: {
    app_id: "APP-LAKSHMI-001",
    basis: "dimension",
    current_composite: 600,
    target_band: "Strong",
    projected_composite: 616,
    projected_band: "Fair",
    reachable: true,
    steps: [
      { feature: "inflow_regularity", plain_label: "Route more sales through bank/UPI", marginal_delta: 9, timeframe_days: 60 },
      { feature: "gst_filing_punctuality", plain_label: "File GST on time for 2+ quarters", marginal_delta: 7, timeframe_days: 90 },
    ],
    disclaimer: "Steps shown in application order. Each delta reflects improvement after prior steps applied. Guidance, not a promise.",
  },
  decision: null,
};

export const MOCK_LEARNING_SUMMARY: LearningSummary = {
  total_decisions: 18,
  overrides_up: 4,
  overrides_down: 1,
  segment_count: 3,
  window_days: 30,
};

export const MOCK_MODEL_VERSIONS: ModelVersion[] = [
  { version: "v-20260601", changed: "Recalibration approved: rec-Kirana/retail-up-20260601", approved_by: "risk_team", ts: "2026-06-01T09:12:00Z", rec_id: "rec-Kirana/retail-up-20260601" },
  { version: "v-20260615", changed: "Recalibration approved: rec-Services-down-20260615", approved_by: "risk_team", ts: "2026-06-15T14:33:00Z", rec_id: "rec-Services-down-20260615" },
];

export const MOCK_RECOMMENDATIONS: RecalRecommendation[] = [
  {
    id: "rec-001",
    segment: "Kirana / retail",
    pattern: "4 up-overrides in 30 days",
    suggestion: "Kirana / retail segment may be under-scored. Consider reviewing cash_flow_health weight for UPI-primary MSMEs.",
    evidence_count: 4,
    status: "pending_human_approval",
  },
];

export const MOCK_AUDIT: AuditEvent[] = [
  { app_id: "MSME0002", ts: "2026-06-13T10:00:00Z", event_type: "data_pull", actor: "consent_ingestion", detail: { consented_scope: ["bank_aa", "gst", "upi", "epfo"] }, consent_ref: "AA-CONSENT-12" },
  { app_id: "MSME0002", ts: "2026-06-13T10:00:05Z", event_type: "score", actor: "scoring_decisioning", detail: { composite: 900, confidence: 0.93 }, model_version: "v0" },
  { app_id: "MSME0002", ts: "2026-06-13T10:00:06Z", event_type: "recommendation", actor: "scoring_decisioning", detail: { eligible: true, amount: 500000 } },
  { app_id: "MSME0002", ts: "2026-06-13T10:00:07Z", event_type: "hitl_request", actor: "orchestrator", detail: { reasons: ["amount > threshold"] } },
];
