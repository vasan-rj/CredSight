// Judge-facing entry screen — the business story, not the architecture. The
// problem (creditworthy MSMEs are invisible to lenders), how CredSight solves it
// in plain language, and the value it creates (time, cost, reach). CTA drops into
// the live demo. Impact figures are illustrative targets modelled on synthetic
// archetypes — no real customer data.

import { Chip, Gauge, Reveal, Ring, SectionLabel } from "./ui";
import { Brand } from "./Brand";

const PROBLEM = [
  {
    t: "No paper, no loan",
    d: "A profitable kirana or workshop with no formal balance sheet and no bureau file gets auto-rejected — not because it can't repay, but because the lender can't see it.",
  },
  {
    t: "Underwriting takes days",
    d: "When a thin file does get a look, an analyst stitches together bank statements, GST and references by hand. Days of work per applicant, and judgement that's hard to audit.",
  },
  {
    t: "Risk hides in the gaps",
    d: "Without cross-checking turnover across sources, gamed numbers and one-off inflow spikes slip through — so lenders price in the doubt or simply walk away.",
  },
];

const SOLUTION = [
  {
    n: "01",
    t: "Share data, with consent",
    d: "The borrower approves access once. CredSight gathers the everyday signals a real business already produces — payments in, sales, filings.",
  },
  {
    n: "02",
    t: "Get a fair, explained score",
    d: "A health score arrives in minutes, in plain language: what makes this business strong, what's risky, and how confident the system is.",
  },
  {
    n: "03",
    t: "Decide with confidence",
    d: "The officer sees a clear recommendation, approves or adjusts, and an offer goes out — with a full record of why, for the risk team and the regulator.",
  },
];

const IMPACT = [
  { n: "< 10 min", l: "from application to a credit offer", sub: "versus 5–7 days of manual review" },
  { n: "₹1,000+", l: "cost saved per assessment", sub: "less analyst time, less paperwork chasing" },
  { n: "4 hrs", l: "officer time saved per file", sub: "data gathered and reconciled for them" },
  { n: "2×", l: "more MSMEs made bankable", sub: "thin-file borrowers become scorable" },
];

export function Landing({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="relative z-10">
      {/* header */}
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6 sm:px-10">
        <Brand />
        <div className="flex items-center gap-3">
          <span className="hidden font-mono text-[12px] text-ink-faint sm:inline">IDBI Innovate 2026 · Track 03</span>
          <Chip tone="emerald">
            <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-current" />
            Financial inclusion
          </Chip>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="mx-auto grid max-w-6xl gap-12 px-6 pb-20 pt-10 sm:px-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:pt-16">
        <div className="flex flex-col justify-center">
          <p className="reveal mb-5 font-mono text-[12px] font-medium uppercase tracking-[0.22em] text-emerald" style={{ animationDelay: "40ms" }}>
            Credit for the businesses banks can't see
          </p>

          <h1
            className="reveal font-display text-[clamp(2.6rem,5.4vw,4.4rem)] font-medium leading-[0.98] tracking-[-0.015em] text-ink"
            style={{ animationDelay: "120ms" }}
          >
            Turn credit-invisible
            <br />
            MSMEs into
            <br />
            <span className="italic text-emerald">bankable borrowers.</span>
          </h1>

          <p className="reveal mt-6 max-w-md text-[17px] leading-relaxed text-ink-soft" style={{ animationDelay: "240ms" }}>
            Millions of small businesses repay reliably but get rejected for lack of a paper trail. CredSight reads
            the signals they already produce, hands the officer a fair score in minutes, and{" "}
            <span className="text-ink">keeps a human in the decision.</span>
          </p>

          <div className="reveal mt-9 flex flex-wrap items-center gap-4" style={{ animationDelay: "360ms" }}>
            <button
              onClick={onEnter}
              className="group inline-flex items-center gap-2.5 rounded-full bg-ink px-6 py-3.5 text-[15px] font-medium text-paper transition hover:bg-emerald-deep"
            >
              See a live assessment
              <span className="transition-transform group-hover:translate-x-0.5">→</span>
            </button>
            <a href="#impact" className="font-mono text-[13px] text-ink-soft underline-offset-4 hover:underline">
              The impact ↓
            </a>
          </div>

          <div className="reveal mt-14 flex flex-wrap gap-x-12 gap-y-5" style={{ animationDelay: "460ms" }}>
            <div>
              <div className="font-display text-2xl font-medium text-ink">Minutes</div>
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">to a credit decision</div>
            </div>
            <div>
              <div className="font-display text-2xl font-medium text-ink">Every decision</div>
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">explained & on record</div>
            </div>
            <div>
              <div className="font-display text-2xl font-medium text-ink">A human</div>
              <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">approves every offer</div>
            </div>
          </div>
        </div>

        {/* product preview */}
        <div className="reveal flex items-center justify-center" style={{ animationDelay: "300ms" }}>
          <div className="w-full max-w-sm">
            <div className="rounded-[24px] border border-line bg-paper p-7 shadow-[0_2px_4px_rgba(26,22,15,0.05),0_40px_80px_-40px_rgba(26,22,15,0.35)]">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <div className="font-display text-lg font-medium text-ink">Lakshmi Stores</div>
                  <div className="font-mono text-[11px] text-ink-faint">Financial Health Card</div>
                </div>
                <Chip tone="amber">Thin file</Chip>
              </div>
              <div className="flex justify-center py-2">
                <Ring score={742} size={184} />
              </div>
              <div className="mt-6 space-y-3.5">
                <Gauge label="Cash-flow health" value={82} delay={500} />
                <Gauge label="GST & turnover" value={71} delay={580} />
                <Gauge label="Banking discipline" value={80} delay={660} />
              </div>
              <div className="mt-6 flex items-center gap-2 border-t border-line pt-4">
                <span className="pulse-dot h-2 w-2 rounded-full bg-amber" />
                <span className="text-[12px] text-ink-soft">
                  Thin file — <span className="text-amber-deep">routed to a human officer.</span>
                </span>
              </div>
            </div>
            <p className="mt-4 text-center font-mono text-[11px] text-ink-faint">
              A borrower the old process would reject — now scored and reviewable.
            </p>
          </div>
        </div>
      </section>

      {/* ── Problem ───────────────────────────────────────────────────── */}
      <section className="border-t border-line bg-paper">
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10">
          <Reveal>
            <SectionLabel>The problem</SectionLabel>
            <h2 className="max-w-2xl font-display text-[clamp(1.9rem,3.6vw,2.8rem)] font-medium leading-[1.05] tracking-[-0.01em] text-ink">
              Creditworthy, but invisible.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-x-12 gap-y-10 md:grid-cols-3">
            {PROBLEM.map((p, i) => (
              <Reveal key={p.t} delay={i * 90} className="border-t-2 border-rose/30 pt-5">
                <h3 className="font-display text-[20px] font-medium text-ink">{p.t}</h3>
                <p className="mt-3 text-[14px] leading-relaxed text-ink-soft">{p.d}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Solution ──────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-20 sm:px-10">
        <Reveal>
          <SectionLabel>The solution</SectionLabel>
          <h2 className="max-w-2xl font-display text-[clamp(1.9rem,3.6vw,2.8rem)] font-medium leading-[1.05] tracking-[-0.01em] text-ink">
            CredSight makes them <span className="italic text-emerald">bankable.</span>
          </h2>
          <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-ink-soft">
            Three steps. The borrower shares data once, an officer gets a fair and explained score, and an offer goes
            out — without the week of manual work, and without losing the human judgement a loan deserves.
          </p>
        </Reveal>
        <div className="mt-12 grid gap-px overflow-hidden rounded-3xl border border-line bg-line md:grid-cols-3">
          {SOLUTION.map((s, i) => (
            <Reveal key={s.n} delay={i * 90} className="flex h-full flex-col bg-paper p-7">
              <span className="font-mono text-[13px] font-semibold text-emerald">{s.n}</span>
              <h3 className="mt-3 font-display text-[21px] font-medium leading-snug text-ink">{s.t}</h3>
              <p className="mt-3 text-[14px] leading-relaxed text-ink-soft">{s.d}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Impact ────────────────────────────────────────────────────── */}
      <section id="impact" className="border-y border-line bg-ink">
        <div className="mx-auto max-w-6xl px-6 py-20 sm:px-10">
          <Reveal>
            <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.22em] text-[#9bc4a8]">The impact</p>
            <h2 className="max-w-2xl font-display text-[clamp(1.9rem,3.6vw,2.8rem)] font-medium leading-[1.05] tracking-[-0.01em] text-paper">
              Faster decisions. Lower cost. More businesses funded.
            </h2>
          </Reveal>
          <div className="mt-14 grid gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
            {IMPACT.map((m, i) => (
              <Reveal key={m.l} delay={(i % 4) * 80}>
                <div className="font-display text-[clamp(2.6rem,5vw,3.6rem)] font-medium leading-none text-paper">{m.n}</div>
                <div className="mt-3 text-[14px] font-medium leading-snug text-paper/85">{m.l}</div>
                <div className="mt-1.5 font-mono text-[11px] leading-snug text-[#9bc4a8]">{m.sub}</div>
              </Reveal>
            ))}
          </div>
          <Reveal>
            <p className="mt-14 font-mono text-[11px] text-paper/40">
              Illustrative targets modelled on synthetic archetypes · no real customer data.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ── Outcome narrative ─────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-6 py-24 text-center sm:px-10">
        <Reveal>
          <SectionLabel>The point of all of it</SectionLabel>
          <p className="font-display text-[clamp(1.8rem,3.8vw,2.9rem)] font-medium leading-[1.12] tracking-[-0.01em] text-ink">
            A kirana owner the system used to reject walks out with a fair offer{" "}
            <span className="italic text-emerald">and a reason for every rupee of it.</span>
          </p>
          <button
            onClick={onEnter}
            className="group mt-10 inline-flex items-center gap-2.5 rounded-full bg-ink px-7 py-4 text-[16px] font-medium text-paper transition hover:bg-emerald-deep"
          >
            See it happen — run a live assessment
            <span className="transition-transform group-hover:translate-x-0.5">→</span>
          </button>
        </Reveal>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-7 sm:px-10">
          <Brand />
          <p className="font-mono text-[11px] text-ink-faint">
            All data synthetic · no real PII, no real money movement · IDBI Innovate 2026 · Track 03
          </p>
        </div>
      </footer>
    </div>
  );
}
