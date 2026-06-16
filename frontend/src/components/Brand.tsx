// Wordmark + monogram. The mark echoes the product's signature object — the
// score ring — so the logo and the Health Card share one geometry.

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
        <circle cx="13" cy="13" r="10" fill="none" stroke="var(--color-line-strong)" strokeWidth="3" />
        {/* ~72% arc, drawn from the top — the "score" portion */}
        <circle
          cx="13"
          cy="13"
          r="10"
          fill="none"
          stroke="var(--color-emerald)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={2 * Math.PI * 10}
          strokeDashoffset={2 * Math.PI * 10 * 0.28}
          transform="rotate(-90 13 13)"
        />
        <circle cx="13" cy="13" r="3" fill="var(--color-ink)" />
      </svg>
      {!compact && (
        <span className="font-display text-[19px] font-medium tracking-[-0.01em] text-ink">CredSight</span>
      )}
    </div>
  );
}
