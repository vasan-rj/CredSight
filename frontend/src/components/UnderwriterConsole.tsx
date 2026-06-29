// The trust centrepiece (golden-demo beat #5): when the orchestrator pauses at the
// HITL gate, the underwriter sees a fully-explained recommendation and approves /
// overrides / requests info. When the run auto-decided (within risk appetite), it
// shows the outcome. No downstream action runs until a human clears the gate.

import { useState } from "react";
import type { RunResult } from "../types";
import { Card, SectionLabel, prettyFeature } from "./ui";

const STATUS: Record<RunResult["status"], { text: string; tone: string; dot: string }> = {
  pending_human: { text: "Human decision required — agent paused, as designed", tone: "border-amber/40 bg-amber-soft text-amber-deep", dot: "bg-amber" },
  approved: { text: "Approved — offer executed", tone: "border-emerald/30 bg-emerald-soft text-emerald-deep", dot: "bg-emerald" },
  rejected: { text: "Rejected", tone: "border-rose/30 bg-rose-soft text-rose-deep", dot: "bg-rose" },
  needs_info: { text: "More information requested", tone: "border-line-strong bg-ink/[0.04] text-ink-soft", dot: "bg-ink-faint" },
};

export function UnderwriterConsole({
  run,
  name,
  onResume,
}: {
  run: RunResult;
  name: string;
  onResume: (decision: "approve" | "override" | "request_info", reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { recommendation: rec, score } = run;
  const status = STATUS[run.status];

  async function decide(decision: "approve" | "override" | "request_info") {
    setSubmitting(true);
    try {
      await onResume(decision, reason);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="reveal overflow-hidden">
      {/* gate banner */}
      <div className={`flex flex-wrap items-center gap-3 border-b px-7 py-4 ${status.tone}`}>
        <span className={`${run.paused ? "pulse-dot" : ""} inline-block h-2.5 w-2.5 rounded-full ${status.dot}`} />
        <span className="font-display text-[17px] font-medium">{status.text}</span>
        {run.reasons.length > 0 && (
          <span className="font-mono text-[12px] opacity-80">· {run.reasons.join("; ")}</span>
        )}
        <span className="ml-auto font-mono text-[12px] opacity-60">{name} · {run.app_id}</span>
      </div>

      <div className="grid gap-px bg-line md:grid-cols-2">
        {/* recommendation */}
        <div className="bg-paper px-7 py-6">
          <SectionLabel>Model recommendation</SectionLabel>
          <div className="mb-5 flex items-baseline gap-3">
            <span className="font-display text-4xl font-medium text-ink tabular-nums">
              {score.composite}
            </span>
            <span className="font-mono text-[12px] text-ink-faint">/ 900 composite</span>
          </div>
          <dl className="divide-y divide-line">
            <Row k="Decision" v={rec.eligible ? "Offer" : "Refer / reject"} />
            <Row k="Product" v={rec.product} />
            <Row k="Amount" v={`₹${rec.amount.toLocaleString("en-IN")}`} strong />
            <Row k="Indicative rate" v={`${rec.indicative_rate}% p.a.`} />
            <Row k="Tenor" v={`${rec.tenor_months} months`} />
            <Row k="Confidence" v={`${(score.confidence * 100).toFixed(0)}%`} />
            {rec.out_of_policy && <Row k="Policy" v="Out of policy" tone="rose" />}
          </dl>
        </div>

        {/* explanation */}
        <div className="bg-paper px-7 py-6">
          <SectionLabel>Why — plain language</SectionLabel>
          <p className="text-[14px] leading-relaxed text-ink-soft">{run.explanation}</p>

          <div className="mt-5">
            <SectionLabel>Top drivers · SHAP</SectionLabel>
          </div>
          <ul className="space-y-1.5">
            {score.shap.map((d) => (
              <li key={d.feature} className="flex items-center justify-between gap-3 text-[13px]">
                <span className="text-ink-soft">{prettyFeature(d.feature)}</span>
                <span className={`font-mono font-medium ${d.direction === "positive" ? "text-emerald" : "text-rose"}`}>
                  {d.shap_value > 0 ? "+" : ""}
                  {d.shap_value.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
          {rec.policy_clause_refs.length > 0 && (
            <p className="mt-4 font-mono text-[11px] text-ink-faint">Policy: {rec.policy_clause_refs.join(", ")}</p>
          )}
        </div>
      </div>

      {/* decision controls */}
      {run.paused ? (
        <div className="border-t border-line bg-amber-soft/40 px-7 py-6">
          <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
            Reason — captured immutably in the audit log
          </label>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Verified GST filings; turnover trend supports the amount."
            className="mb-4 w-full rounded-xl border border-line-strong bg-paper px-4 py-2.5 text-[14px] text-ink placeholder:text-ink-faint focus:border-emerald focus:outline-none focus:ring-2 focus:ring-emerald/20"
          />
          <div className="flex flex-wrap gap-3">
            <button
              disabled={submitting}
              onClick={() => decide("approve")}
              className="rounded-full bg-emerald px-5 py-2.5 text-[14px] font-medium text-paper transition hover:bg-emerald-deep disabled:opacity-50"
            >
              Approve & execute offer
            </button>
            <button
              disabled={submitting}
              onClick={() => decide("override")}
              className="rounded-full border border-rose/40 bg-rose-soft px-5 py-2.5 text-[14px] font-medium text-rose-deep transition hover:bg-rose/10 disabled:opacity-50"
            >
              Override (reject)
            </button>
            <button
              disabled={submitting}
              onClick={() => decide("request_info")}
              className="rounded-full border border-line-strong bg-paper px-5 py-2.5 text-[14px] font-medium text-ink-soft transition hover:border-ink/30 hover:text-ink disabled:opacity-50"
            >
              Request info
            </button>
          </div>
        </div>
      ) : (
        run.decision && (
          <div className="border-t border-line px-7 py-5 font-mono text-[13px] text-ink-soft">
            Decision <span className="font-semibold text-ink">{run.decision.decision}</span> by {run.decision.underwriter}
            {run.decision.reason ? ` — "${run.decision.reason}"` : ""}.
          </div>
        )
      )}
    </Card>
  );
}

function Row({ k, v, strong, tone }: { k: string; v: string; strong?: boolean; tone?: "rose" }) {
  return (
    <div className="flex items-center justify-between py-2">
      <dt className="text-[13px] text-ink-faint">{k}</dt>
      <dd
        className={`font-mono text-[13px] ${strong ? "text-[15px] font-semibold" : "font-medium"} ${
          tone === "rose" ? "text-rose" : "text-ink"
        }`}
      >
        {v}
      </dd>
    </div>
  );
}
