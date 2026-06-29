// API client — drives the CredSight orchestrator (LangGraph) endpoints. Flip USE_MOCK to
// run the UI standalone against src/mock.ts.

import type {
  AuditEvent, CatalogItem, LearningSummary, ModelVersion, RecalRecommendation, RunResult,
  UploadPreview,
} from "./types";
import {
  CATALOG, MOCK_AUDIT, MOCK_LEARNING_SUMMARY, MOCK_MODEL_VERSIONS, MOCK_RECOMMENDATIONS,
  MOCK_RUN, MOCK_RUN_LAKSHMI,
} from "./mock";

const USE_MOCK = false;

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return http<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  getCatalog: (): Promise<CatalogItem[]> =>
    USE_MOCK ? Promise.resolve(CATALOG) : http("/catalog"),

  // Start an assessment through the orchestrator graph (ingest -> reconcile -> score ->
  // HITL gate -> action). Returns the full result + whether it paused for a human.
  runAssessment: (item: CatalogItem): Promise<RunResult> =>
    USE_MOCK
      ? Promise.resolve(item.archetype === "thin_file" ? MOCK_RUN_LAKSHMI : MOCK_RUN)
      : post("/orchestrator/run", {
          app_id: item.app_id,
          archetype: item.archetype,
          seed: item.seed,
          name: item.name,
        }),

  // Resume a paused run with the underwriter's decision; runs to completion.
  resumeRun: (
    appId: string,
    decision: "approve" | "override" | "request_info",
    reason: string,
    currentRun: RunResult,
  ): Promise<RunResult> =>
    USE_MOCK
      ? Promise.resolve({
          ...currentRun, paused: false,
          status: decision === "approve" ? "approved" : decision === "override" ? "rejected" : "needs_info",
          decision: { decision, reason, underwriter: "underwriter:demo" },
        })
      : post("/orchestrator/resume", { app_id: appId, decision, reason }),

  getAudit: (appId: string): Promise<AuditEvent[]> =>
    USE_MOCK ? Promise.resolve(MOCK_AUDIT) : http(`/orchestrator/${appId}/audit`),

  // ── Learning Loop (D2) ──────────────────────────────────────────────────────

  getLearningSummary: (): Promise<LearningSummary> =>
    USE_MOCK ? Promise.resolve(MOCK_LEARNING_SUMMARY) : http("/learning/summary"),

  getLearningRecommendations: (): Promise<RecalRecommendation[]> =>
    USE_MOCK ? Promise.resolve(MOCK_RECOMMENDATIONS) : http("/learning/recommendations"),

  approveRecommendation: (recId: string): Promise<{ ok: boolean }> =>
    USE_MOCK
      ? Promise.resolve({ ok: true })
      : post(`/learning/recommendations/${recId}/approve`, {}),

  getModelVersions: (): Promise<ModelVersion[]> =>
    USE_MOCK ? Promise.resolve(MOCK_MODEL_VERSIONS) : http("/learning/model-versions"),

  // Upload path — judges drag in their own files; scoring + HITL unchanged.
  parseUpload: (
    appId: string, name: string, sector: string,
    bankCsv: File | null, gstData: File | null, upiCsv: File | null,
    gstin?: string,
  ): Promise<{ app_id: string; preview: UploadPreview }> => {
    if (USE_MOCK) {
      return Promise.resolve({
        app_id: appId,
        preview: { sources_found: ["bank_aa", "gst"], missing_sources: ["upi", "epfo", "bureau"],
                   months_bank: 12, months_gst: 12, upi_txn_count: 0, turnover_estimate: 450000 },
      });
    }
    const fd = new FormData();
    fd.append("app_id", appId);
    fd.append("name", name);
    fd.append("sector", sector);
    if (gstin) fd.append("gstin", gstin);
    if (bankCsv) fd.append("bank_csv", bankCsv);
    if (gstData) fd.append("gst_data", gstData);
    if (upiCsv) fd.append("upi_csv", upiCsv);
    return http<{ app_id: string; preview: UploadPreview }>("/upload/parse", { method: "POST", body: fd });
  },

  lookupGstin: (gstin: string): Promise<{
    legal_name?: string; trade_name?: string; state?: string;
    status?: string; registration_date?: string; business_type?: string;
  }> =>
    USE_MOCK ? Promise.resolve({}) : http(`/gstin/${encodeURIComponent(gstin)}`),

  runUpload: (appId: string, name: string): Promise<RunResult> =>
    USE_MOCK
      ? Promise.resolve({ ...MOCK_RUN_LAKSHMI, app_id: appId })
      : http<RunResult>("/upload/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ app_id: appId, name }),
        }),
};
