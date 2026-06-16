// The hero screen (golden-demo beat #4): composite score, five dimension gauges,
// plain-language strengths/risks from the model's SHAP drivers, and an honest
// confidence indicator. Framed as a financial credential, not a dashboard widget.

import type { Dimension, ScoreResult } from "../types";
import { Card, Chip, Gauge, Ring, SectionLabel, band, prettyFeature } from "./ui";

const DIM_LABELS: Record<Dimension, string> = {
  cash_flow_health: "Cash-flow health",
  gst_turnover_signal: "GST & turnover",
  banking_discipline: "Banking discipline",
  business_vintage_stability: "Vintage & stability",
  obligation_load_formality: "Obligation load",
};

function Confidence({ confidence }: { confidence: number }) {
  const low = confidence < 0.7;
  const pct = Math.round(confidence * 100);
  return (
    <div className={`rounded-xl border px-4 py-3 ${low ? "border-amber/40 bg-amber-soft" : "border-emerald/30 bg-emerald-soft"}`}>
      <div className="flex items-baseline justify-between gap-6">
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">Confidence</span>
        <span className={`font-mono text-[15px] font-semibold ${low ? "text-amber-deep" : "text-emerald-deep"}`}>{pct}%</span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-paper/70">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: low ? "var(--color-amber)" : "var(--color-emerald)" }} />
      </div>
      <p className={`mt-2 text-[12px] leading-snug ${low ? "text-amber-deep" : "text-emerald-deep"}`}>
        {low ? "Thin file — routed to a human underwriter." : "Sufficient data across sources."}
      </p>
    </div>
  );
}

export function HealthCard({ score, name }: { score: ScoreResult; name: string }) {
  const strengths = score.shap.filter((d) => d.direction === "positive").slice(0, 3);
  const risks = score.shap.filter((d) => d.direction === "negative").slice(0, 3);
  const verdict = band(score.composite);

  return (
    <Card className="reveal overflow-hidden">
      {/* masthead */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-7 py-6">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint">Financial Health Card</p>
          <h2 className="mt-1.5 font-display text-3xl font-medium tracking-[-0.01em] text-ink">{name}</h2>
          <p className="mt-1 font-mono text-[12px] text-ink-faint">
            model {score.model_version} · {score.app_id}
          </p>
        </div>
        <Chip tone={verdict.label === "Refer" ? "rose" : verdict.label === "Fair" ? "amber" : "emerald"}>
          {verdict.label}
        </Chip>
      </div>

      <div className="grid gap-8 px-7 py-7 md:grid-cols-[260px_1fr] md:gap-10">
        {/* score */}
        <div className="flex flex-col items-center gap-5">
          <Ring score={score.composite} />
          <div className="w-full">
            <Confidence confidence={score.confidence} />
          </div>
        </div>

        {/* dimensions */}
        <div>
          <SectionLabel>Five scored dimensions</SectionLabel>
          <div className="space-y-4">
            {(Object.keys(DIM_LABELS) as Dimension[]).map((d, i) => (
              <Gauge key={d} label={DIM_LABELS[d]} value={score.dimensions[d]} delay={i * 80} />
            ))}
          </div>
        </div>
      </div>

      {/* strengths / risks */}
      <div className="grid gap-px border-t border-line bg-line md:grid-cols-2">
        <div className="bg-paper px-7 py-6">
          <SectionLabel>What supports this score</SectionLabel>
          <ul className="space-y-2.5">
            {strengths.map((d) => (
              <li key={d.feature} className="flex items-center gap-2.5 text-[14px] text-ink">
                <span className="font-mono text-emerald">↑</span>
                {prettyFeature(d.feature)}
              </li>
            ))}
            {strengths.length === 0 && <li className="text-[13px] text-ink-faint">No positive drivers surfaced.</li>}
          </ul>
        </div>
        <div className="bg-paper px-7 py-6">
          <SectionLabel>What weakens it</SectionLabel>
          <ul className="space-y-2.5">
            {risks.map((d) => (
              <li key={d.feature} className="flex items-center gap-2.5 text-[14px] text-ink">
                <span className="font-mono text-rose">↓</span>
                {prettyFeature(d.feature)}
              </li>
            ))}
            {risks.length === 0 && <li className="text-[13px] text-ink-faint">No material risk drivers.</li>}
          </ul>
        </div>
      </div>
    </Card>
  );
}
