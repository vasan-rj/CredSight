// NeedsCard (D5) — shows the business-needs headline, evidence chips, matched products,
// and a consent CTA (for gst_only cases). Renders above the HealthCard when needs are set.

import type { NeedsAssessment, ProductMatch } from "../types";

const URGENCY_LABEL: Record<string, string> = {
  immediate: "Immediate need",
  medium_term: "Medium-term",
  planning: "Planning stage",
};

const NEED_ICON: Record<string, string> = {
  working_capital: "↺",
  seasonal: "◈",
  capex: "▲",
  trade_finance: "⇄",
};

function fmt(n: number): string {
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(1).replace(/\.0$/, "")}L`;
  return `₹${Math.round(n / 1000)}K`;
}

function ProductCard({ pm }: { pm: ProductMatch }) {
  const eligible = pm.score_band_ok;
  return (
    <div
      className={`rounded-xl border p-4 ${
        eligible ? "border-emerald/40 bg-emerald/5" : "border-line bg-paper opacity-70"
      }`}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-[13px] font-semibold text-ink">{pm.name}</p>
          <p className="font-mono text-[11px] text-ink-faint">{pm.tagline}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-[14px] font-bold text-emerald">{fmt(pm.amount_estimate)}</p>
          <p className="font-mono text-[11px] text-ink-faint">
            {pm.tenor_range[0]}–{pm.tenor_range[1]}m · {pm.indicative_rate}% p.a.
          </p>
        </div>
      </div>

      <p className="mb-3 text-[12px] text-ink-soft">{pm.fit_reason}</p>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {pm.key_features.map((f) => (
          <span
            key={f}
            className="rounded-full border border-line bg-paper px-2 py-0.5 font-mono text-[10px] text-ink-faint"
          >
            {f}
          </span>
        ))}
      </div>

      <div className="flex items-center gap-1.5">
        {pm.data_needed.map((d) => (
          <span
            key={d}
            className="rounded border border-line px-1.5 py-0.5 font-mono text-[10px] text-ink-faint"
          >
            {d.toUpperCase()}
          </span>
        ))}
        {pm.score_required && !eligible && (
          <span className="ml-auto font-mono text-[10px] text-amber-deep">
            Score required
          </span>
        )}
        {eligible && (
          <span className="ml-auto font-mono text-[10px] text-emerald">
            ✓ Eligible now
          </span>
        )}
      </div>
    </div>
  );
}

interface Props {
  needs: NeedsAssessment;
  productMatches: ProductMatch[];
}

export function NeedsCard({ needs, productMatches }: Props) {
  const icon = NEED_ICON[needs.need_type] ?? "◆";
  const urgency = URGENCY_LABEL[needs.urgency] ?? needs.urgency;

  return (
    <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
      {/* headline */}
      <div className="mb-5 flex items-start gap-3">
        <span className="mt-0.5 text-[22px] leading-none text-emerald">{icon}</span>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-ink-faint">
            Business Need Identified
          </p>
          <p className="mt-1 text-[17px] font-semibold text-ink">{needs.headline}</p>
          <span className="mt-1 inline-block rounded-full border border-amber/40 bg-amber/10 px-2.5 py-0.5 font-mono text-[11px] text-amber-deep">
            {urgency}
          </span>
        </div>
      </div>

      {/* evidence chips */}
      {needs.evidence.length > 0 && (
        <div className="mb-5 flex flex-wrap gap-1.5">
          {needs.evidence.map((e) => (
            <span
              key={e}
              className="rounded-full border border-line bg-paper px-2.5 py-0.5 font-mono text-[11px] text-ink-faint"
            >
              {e}
            </span>
          ))}
        </div>
      )}

      {/* product matches */}
      {productMatches.length > 0 && (
        <div className="mb-4">
          <p className="mb-3 text-[12px] font-semibold uppercase tracking-widest text-ink-faint">
            Matched Products
          </p>
          <div className="space-y-3">
            {productMatches.map((pm) => (
              <ProductCard key={pm.product_id} pm={pm} />
            ))}
          </div>
        </div>
      )}

      {/* consent CTA */}
      {needs.gst_only && needs.consent_to_unlock.length > 0 && (
        <div className="mt-4 rounded-xl border border-emerald/30 bg-emerald/5 px-4 py-3">
          <p className="mb-1 text-[12px] font-semibold text-emerald">
            Share more data for a precise score
          </p>
          <ul className="space-y-0.5">
            {needs.consent_to_unlock.map((item) => (
              <li key={item} className="font-mono text-[11px] text-ink-soft">
                + {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
