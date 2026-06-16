// Shared "Ledger" primitives — the score ring, dimension gauges, chips, and the
// band logic (composite -> color + label). Reused by HealthCard and the Landing
// preview so the visual language is defined once.

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

// ── Reveal ───────────────────────────────────────────────────────────────
// Entrance animation that ALWAYS ends visible (animation-fill: forwards). It
// fires on mount rather than on scroll — deliberately: gating on an observer
// risks leaving below-fold content stuck invisible on fast scroll or capture.
// Below-fold sections animate while off-screen and simply read as present once
// scrolled to. prefers-reduced-motion short-circuits to fully visible (in CSS).

export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <div className={`reveal ${className}`} style={{ animationDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

// ── Band logic ────────────────────────────────────────────────────────────
// 300–900 composite -> a palette colour + a one-word verdict. Mirrors the
// thresholds the deterministic scorer uses (HealthCard previously inlined these).

export type Band = { label: string; color: string; soft: string };

export function band(composite: number): Band {
  if (composite >= 750) return { label: "Strong", color: "var(--color-emerald)", soft: "var(--color-emerald-soft)" };
  if (composite >= 680) return { label: "Good", color: "#3f7a45", soft: "var(--color-emerald-soft)" };
  if (composite >= 600) return { label: "Fair", color: "var(--color-amber)", soft: "var(--color-amber-soft)" };
  return { label: "Refer", color: "var(--color-rose)", soft: "var(--color-rose-soft)" };
}

// ── Count-up ──────────────────────────────────────────────────────────────
// Eases a number from `from` to `to` once on mount / when `to` changes. Gives
// the composite score its "settling" feel without a dependency.

export function useCountUp(to: number, from = 300, duration = 1150): number {
  const [v, setV] = useState(from);
  const raf = useRef(0);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setV(Math.round(from + (to - from) * eased));
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [to, from, duration]);
  return v;
}

// ── Score ring ─────────────────────────────────────────────────────────────

export function Ring({
  score,
  size = 208,
  stroke = 14,
  showLabel = true,
}: {
  score: number;
  size?: number;
  stroke?: number;
  showLabel?: boolean;
}) {
  const pct = Math.max(0, Math.min(1, (score - 300) / 600));
  const r = (size - stroke) / 2 - 2;
  const circ = 2 * Math.PI * r;
  const dash = circ * (1 - pct);
  const { label, color } = band(score);
  const display = useCountUp(score);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg
        viewBox={`0 0 ${size} ${size}`}
        style={{ width: size, height: size, transform: "rotate(-90deg)" }}
      >
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-line)" strokeWidth={stroke} />
        <circle
          key={score}
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          className="ring-anim"
          style={{ ["--circ" as string]: circ, ["--dash" as string]: dash } as CSSProperties}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="font-display tabular-nums leading-none"
          style={{ color, fontSize: size * 0.3, fontWeight: 500 }}
        >
          {display}
        </span>
        <span className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint">/ 900</span>
        {showLabel && (
          <span
            className="mt-2 rounded-full px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.15em]"
            style={{ color, backgroundColor: band(score).soft }}
          >
            {label}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Dimension gauge ──────────────────────────────────────────────────────

export function Gauge({ label, value, delay = 0 }: { label: string; value: number; delay?: number }) {
  const v = Math.max(0, Math.min(100, value));
  // Tint the fill by strength so the five gauges read at a glance.
  const color = v >= 75 ? "var(--color-emerald)" : v >= 55 ? "#7a7c2f" : "var(--color-amber)";
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-[13px] text-ink-soft">{label}</span>
        <span className="font-mono text-[13px] font-medium text-ink">{v.toFixed(0)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-line">
        <div
          key={value}
          className="bar-anim h-full rounded-full"
          style={{ ["--w" as string]: v / 100, backgroundColor: color, animationDelay: `${delay}ms` } as CSSProperties}
        />
      </div>
    </div>
  );
}

// ── Chip ────────────────────────────────────────────────────────────────

type Tone = "ink" | "emerald" | "amber" | "rose" | "azure";

const CHIP: Record<Tone, string> = {
  ink: "bg-ink/[0.06] text-ink-soft",
  emerald: "bg-emerald-soft text-emerald-deep",
  amber: "bg-amber-soft text-amber-deep",
  rose: "bg-rose-soft text-rose-deep",
  azure: "bg-azure-soft text-azure",
};

export function Chip({ tone = "ink", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] ${CHIP[tone]}`}
    >
      {children}
    </span>
  );
}

// ── Section label — the small mono kicker over a block ──────────────────────

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.22em] text-ink-faint">{children}</p>
  );
}

// ── Card — the paper surface ───────────────────────────────────────────────

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={`rounded-[var(--radius-card)] border border-line bg-paper shadow-[0_1px_2px_rgba(26,22,15,0.04),0_12px_30px_-18px_rgba(26,22,15,0.18)] ${className}`}
    >
      {children}
    </div>
  );
}

// Humanise a SHAP feature key: "gst_filing_punctuality" -> "GST filing punctuality".
export function prettyFeature(f: string): string {
  const s = f.replace(/_/g, " ").replace(/\bnorm\b/, "").trim();
  return s.replace(/\bgst\b/i, "GST").replace(/\bupi\b/i, "UPI").replace(/\bemi\b/i, "EMI").replace(/^./, (c) => c.toUpperCase());
}
