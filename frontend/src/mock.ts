// Mock data so the UI runs standalone (USE_MOCK=true in api.ts) before the backend is up.

import type { AuditEvent, CatalogItem, RunResult } from "./types";

export const CATALOG: CatalogItem[] = [
  { app_id: "APP-LAKSHMI-001", name: "Lakshmi Stores", archetype: "thin_file", seed: 101, sector: "Kirana / retail" },
  { app_id: "MSME0002", name: "Sri Auto Works", archetype: "strong", seed: 102, sector: "Micro-manufacturing" },
  { app_id: "MSME0005", name: "Anand Tailors", archetype: "stressed", seed: 103, sector: "Services" },
  { app_id: "MSME0007", name: "Deccan Traders", archetype: "fraud", seed: 104, sector: "Wholesale" },
];

export const MOCK_RUN: RunResult = {
  app_id: "MSME0002",
  status: "pending_human",
  paused: true,
  reasons: ["amount 500,000 > threshold 200,000"],
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
  decision: null,
};

export const MOCK_AUDIT: AuditEvent[] = [
  { app_id: "MSME0002", ts: "2026-06-13T10:00:00Z", event_type: "data_pull", actor: "consent_ingestion", detail: { consented_scope: ["bank_aa", "gst", "upi", "epfo"] }, consent_ref: "AA-CONSENT-12" },
  { app_id: "MSME0002", ts: "2026-06-13T10:00:05Z", event_type: "score", actor: "scoring_decisioning", detail: { composite: 900, confidence: 0.93 }, model_version: "v0" },
  { app_id: "MSME0002", ts: "2026-06-13T10:00:06Z", event_type: "recommendation", actor: "scoring_decisioning", detail: { eligible: true, amount: 500000 } },
  { app_id: "MSME0002", ts: "2026-06-13T10:00:07Z", event_type: "hitl_request", actor: "orchestrator", detail: { reasons: ["amount > threshold"] } },
];
