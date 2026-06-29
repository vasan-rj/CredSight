// Path-to-Bankability (D1) — renders below the Health Card for sub-Strong applicants.
// Shows the deterministic model's greedy counterfactual path to the next credit band.

import type { Pathway } from "../types";

const BAND_COLOR: Record<string, string> = {
  Strong:  "text-emerald",
  Good:    "text-azure",
  Fair:    "text-amber-deep",
  Refer:   "text-rose-600",
};

function bandColor(band: string): string {
  return BAND_COLOR[band] ?? "text-ink";
}

function DeltaRing({ delta, total }: { delta: number; total: number }) {
  const pct = Math.min(delta / Math.max(total, 1), 1);
  const r = 16;
  const circ = 2 * Math.PI * r;
  const dash = pct * circ;
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" className="shrink-0">
      <circle cx="20" cy="20" r={r} fill="none" stroke="var(--color-line)" strokeWidth="3" />
      <circle
        cx="20" cy="20" r={r} fill="none"
        stroke="var(--color-emerald)" strokeWidth="3"
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 20 20)"
      />
      <text x="20" y="24" textAnchor="middle" className="fill-ink font-mono text-[9px]" fontSize="9">
        +{delta}
      </text>
    </svg>
  );
}

interface Props {
  pathway: Pathway;
}

export function PathToBankability({ pathway }: Props) {
  const { steps, reachable, current_composite, projected_composite, target_band, disclaimer } = pathway;
  const totalDelta = projected_composite - current_composite;

  if (!reachable && steps.length === 0) {
    return (
      <section id="path-to-bankability" className="mt-8 rounded-xl border border-line bg-paper p-6">
        <h2 className="mb-1 text-[15px] font-semibold text-ink">Raise your score</h2>
        <p className="font-mono text-[13px] text-ink-faint">
          No borrower-controllable path to <span className={bandColor(target_band)}>{target_band}</span> detected
          from current data. More history or a different product may qualify.
        </p>
      </section>
    );
  }

  return (
    <section id="path-to-bankability" className="mt-8 rounded-xl border border-line bg-paper p-6">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Raise your score</h2>
          <p className="mt-0.5 font-mono text-[12px] text-ink-faint">
            Deterministic model · {steps.length} action{steps.length !== 1 ? "s" : ""}
            {reachable
              ? <> · projected <span className={bandColor(target_band)}>{target_band}</span></>
              : <> · improves score, may not reach {target_band}</>}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <span className="font-mono text-[22px] font-bold text-ink">{current_composite}</span>
          <span className="mx-1 font-mono text-[13px] text-ink-faint">→</span>
          <span className={`font-mono text-[22px] font-bold ${reachable ? bandColor(target_band) : "text-ink-soft"}`}>
            {projected_composite}
          </span>
          <p className="mt-0.5 font-mono text-[11px] text-ink-faint">composite score</p>
        </div>
      </div>

      <ol className="space-y-3">
        {steps.map((step, i) => (
          <li key={step.feature} className="flex items-center gap-4 rounded-lg border border-line px-4 py-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald/10 font-mono text-[11px] font-semibold text-emerald">
              {i + 1}
            </span>
            <DeltaRing delta={step.marginal_delta} total={totalDelta} />
            <div className="flex-1">
              <p className="text-[14px] font-medium text-ink">{step.plain_label}</p>
              <p className="font-mono text-[11px] text-ink-faint">
                ~{step.timeframe_days}d · +{step.marginal_delta} pts
              </p>
            </div>
          </li>
        ))}
      </ol>

      <p className="mt-4 font-mono text-[11px] text-ink-faint">{disclaimer}</p>
    </section>
  );
}
