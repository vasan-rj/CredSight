// Golden-demo beat #7: every action traceable. Renders the append-only audit log
// (governance/audit.py) — consent ref, data pulls, recon flags, score, HITL, decision.
// Reads as an immutable ledger: mono throughout, source + model + human on every line.

import type { AuditEvent } from "../types";
import { Card, SectionLabel } from "./ui";

const TYPE_TONE: Record<string, { dot: string; chip: string }> = {
  consent: { dot: "bg-azure", chip: "bg-azure-soft text-azure" },
  data_pull: { dot: "bg-azure", chip: "bg-azure-soft text-azure" },
  recon_flag: { dot: "bg-amber", chip: "bg-amber-soft text-amber-deep" },
  score: { dot: "bg-emerald", chip: "bg-emerald-soft text-emerald-deep" },
  recommendation: { dot: "bg-emerald", chip: "bg-emerald-soft text-emerald-deep" },
  hitl_request: { dot: "bg-amber", chip: "bg-amber-soft text-amber-deep" },
  human_decision: { dot: "bg-emerald", chip: "bg-emerald-soft text-emerald-deep" },
  action: { dot: "bg-emerald", chip: "bg-emerald-soft text-emerald-deep" },
  error: { dot: "bg-rose", chip: "bg-rose-soft text-rose-deep" },
};

const FALLBACK = { dot: "bg-ink-faint", chip: "bg-ink/[0.06] text-ink-soft" };

export function AuditTrail({ events }: { events: AuditEvent[] }) {
  return (
    <Card className="reveal px-7 py-7">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <SectionLabel>Audit trail</SectionLabel>
          <p className="-mt-1 text-[14px] text-ink-soft">
            Append-only · every step traceable to source, model version, and human.
          </p>
        </div>
        <span className="font-mono text-[12px] text-ink-faint">{events.length} events</span>
      </div>

      {events.length === 0 ? (
        <p className="font-mono text-[13px] text-ink-faint">No events yet — run an applicant.</p>
      ) : (
        <ol className="relative ml-1 border-l border-line pl-6">
          {events.map((e, i) => {
            const tone = TYPE_TONE[e.event_type] ?? FALLBACK;
            return (
              <li key={i} className="mb-6 last:mb-0">
                <span className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-paper ${tone.dot}`} />
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className={`rounded-md px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.06em] ${tone.chip}`}>
                    {e.event_type}
                  </span>
                  <span className="font-mono text-[12px] font-medium text-ink">{e.actor}</span>
                  <span className="ml-auto font-mono text-[11px] text-ink-faint">{e.ts}</span>
                </div>
                <pre className="mt-2 overflow-x-auto rounded-lg border border-line bg-ivory/60 px-3 py-2 font-mono text-[12px] leading-relaxed text-ink-soft">
                  {JSON.stringify(e.detail, null, 0)}
                </pre>
                {(e.consent_ref || e.model_version) && (
                  <div className="mt-1.5 flex gap-4 font-mono text-[11px] text-ink-faint">
                    {e.consent_ref && <span>consent: {e.consent_ref}</span>}
                    {e.model_version && <span>model: {e.model_version}</span>}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
