// Learning Loop (D2) — decision capture summary + pending recalibration recommendations.
// Underwriters see how their overrides are being tracked and can approve pattern-based
// recalibration recommendations before they reach the model team.

import { useEffect, useState } from "react";
import { api } from "../api";
import type { LearningSummary, ModelVersion, RecalRecommendation } from "../types";
import { Chip } from "./ui";

function StatBox({ label, value, tone }: { label: string; value: number; tone?: "emerald" | "amber" | "rose" }) {
  const toneClass = tone === "emerald" ? "text-emerald" : tone === "amber" ? "text-amber-deep" : tone === "rose" ? "text-rose-600" : "text-ink";
  return (
    <div className="rounded-lg border border-line bg-paper px-5 py-4">
      <p className={`font-mono text-[28px] font-bold ${toneClass}`}>{value}</p>
      <p className="mt-0.5 font-mono text-[11px] text-ink-faint">{label}</p>
    </div>
  );
}

interface RecCardProps {
  rec: RecalRecommendation;
  onApprove: (id: string) => Promise<void>;
}

function RecCard({ rec, onApprove }: RecCardProps) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(rec.status !== "pending_human_approval");

  const approve = async () => {
    setBusy(true);
    await onApprove(rec.id);
    setDone(true);
    setBusy(false);
  };

  return (
    <div className="rounded-xl border border-line bg-paper p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-[14px] font-semibold text-ink">{rec.segment}</p>
          <p className="mt-0.5 font-mono text-[12px] text-ink-faint">{rec.pattern}</p>
        </div>
        <Chip tone={done ? "emerald" : "amber"}>
          {done ? "approved" : `${rec.evidence_count} signals`}
        </Chip>
      </div>
      <p className="mb-4 text-[13px] text-ink-soft">{rec.suggestion}</p>
      {!done && (
        <button
          onClick={approve}
          disabled={busy}
          className="rounded-lg border border-emerald px-4 py-1.5 font-mono text-[12px] font-semibold text-emerald transition hover:bg-emerald/10 disabled:opacity-50"
        >
          {busy ? "saving…" : "Approve recommendation"}
        </button>
      )}
    </div>
  );
}

function ModelVersionHistory({ versions }: { versions: ModelVersion[] }) {
  if (versions.length === 0) {
    return (
      <p className="font-mono text-[12px] text-ink-faint">
        No recalibrations approved yet — approvals appear here as an immutable timeline.
      </p>
    );
  }
  return (
    <ol className="space-y-3">
      {versions.map((v) => (
        <li key={v.rec_id} className="flex items-start gap-4 rounded-lg border border-line bg-paper px-4 py-3">
          <span className="shrink-0 rounded bg-emerald/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-emerald">
            {v.version}
          </span>
          <div className="flex-1 min-w-0">
            <p className="truncate text-[13px] text-ink">{v.changed}</p>
            <p className="font-mono text-[11px] text-ink-faint">
              {v.approved_by} · {new Date(v.ts).toLocaleDateString()}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function LearningLoop() {
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [recs, setRecs] = useState<RecalRecommendation[]>([]);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getLearningSummary(),
      api.getLearningRecommendations(),
      api.getModelVersions(),
    ])
      .then(([s, r, v]) => { setSummary(s); setRecs(r); setVersions(v); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleApprove = async (id: string) => {
    await api.approveRecommendation(id);
    // Refresh model versions after approval.
    api.getModelVersions().then(setVersions).catch(() => {});
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 font-mono text-[13px] text-ink-faint">
        <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-amber" />
        Loading learning loop…
      </div>
    );
  }

  if (error) {
    return <p className="font-mono text-[13px] text-rose-600">Error: {error}</p>;
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="mb-1 text-[18px] font-semibold text-ink">Learning Loop</h2>
        <p className="font-mono text-[12px] text-ink-faint">
          Every human override is captured. Patterns accumulate and surface as recalibration
          recommendations — none reach the model without explicit human approval.
        </p>
      </div>

      {summary && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatBox label="decisions captured" value={summary.total_decisions} />
            <StatBox label="up-overrides" value={summary.overrides_up} tone="amber" />
            <StatBox label="down-overrides" value={summary.overrides_down} tone="rose" />
            <StatBox label="segments tracked" value={summary.segment_count} tone="emerald" />
          </div>
          <p className="font-mono text-[12px] text-ink-faint">
            Collecting patterns: {summary.total_decisions} decision{summary.total_decisions !== 1 ? "s" : ""} across {summary.segment_count} segment{summary.segment_count !== 1 ? "s" : ""}
            {" "}· last {summary.window_days} days
          </p>
        </>
      )}

      <div>
        <h3 className="mb-4 text-[15px] font-semibold text-ink">
          Recalibration Recommendations
          {recs.length > 0 && (
            <span className="ml-2 rounded-full bg-amber/20 px-2 py-0.5 font-mono text-[11px] text-amber-deep">
              {recs.filter((r) => r.status === "pending_human_approval").length} pending
            </span>
          )}
        </h3>

        {recs.length === 0 ? (
          <div className="rounded-xl border border-line bg-paper px-6 py-8 text-center">
            <p className="font-mono text-[13px] text-ink-faint">
              No patterns detected yet — {summary?.window_days ?? 30}-day window needs ≥ {8} signals per segment.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {recs.map((r) => (
              <RecCard key={r.id} rec={r} onApprove={handleApprove} />
            ))}
          </div>
        )}
      </div>

      <div>
        <h3 className="mb-4 text-[15px] font-semibold text-ink">Recalibration History</h3>
        <ModelVersionHistory versions={versions} />
      </div>

      <p className="border-t border-line pt-4 font-mono text-[11px] text-ink-faint">
        The model never auto-updates. Every recalibration requires explicit human approval before reaching the model team.
      </p>
    </div>
  );
}
