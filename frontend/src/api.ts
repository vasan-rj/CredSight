// API client — drives the CredSight orchestrator (LangGraph) endpoints. Flip USE_MOCK to
// run the UI standalone against src/mock.ts.

import type { AuditEvent, CatalogItem, RunResult } from "./types";
import { CATALOG, MOCK_AUDIT, MOCK_RUN } from "./mock";

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
      ? Promise.resolve(MOCK_RUN)
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
  ): Promise<RunResult> =>
    USE_MOCK
      ? Promise.resolve({ ...MOCK_RUN, paused: false, status: decision === "approve" ? "approved" : decision === "override" ? "rejected" : "needs_info", decision: { decision, reason, underwriter: "underwriter:demo" } })
      : post("/orchestrator/resume", { app_id: appId, decision, reason }),

  getAudit: (appId: string): Promise<AuditEvent[]> =>
    USE_MOCK ? Promise.resolve(MOCK_AUDIT) : http(`/orchestrator/${appId}/audit`),
};
