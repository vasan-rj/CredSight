// Demo shell — drives a LIVE orchestrator run. Landing → pick an applicant → the
// agent runs ingest → reconcile → score → HITL gate → action; the tabs show the
// golden path (Health Card, Underwriter Console, Audit Trail) for the selected run.

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { HealthCard } from "./components/HealthCard";
import { UnderwriterConsole } from "./components/UnderwriterConsole";
import { AuditTrail } from "./components/AuditTrail";
import { Catalog } from "./components/Portfolio";
import { Landing } from "./components/Landing";
import { Brand } from "./components/Brand";
import { Chip } from "./components/ui";
import type { AuditEvent, CatalogItem, RunResult } from "./types";

type Tab = "card" | "console" | "audit" | "catalog";

const TABS: { id: Tab; label: string }[] = [
  { id: "card", label: "Health Card" },
  { id: "console", label: "Underwriter Console" },
  { id: "audit", label: "Audit Trail" },
  { id: "catalog", label: "Applicants" },
];

const ARCH_TONE: Record<CatalogItem["archetype"], "azure" | "emerald" | "amber" | "rose"> = {
  thin_file: "azure",
  strong: "emerald",
  stressed: "amber",
  fraud: "rose",
};

export default function App() {
  const [entered, setEntered] = useState(false);
  const [tab, setTab] = useState<Tab>("card");
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [selected, setSelected] = useState<CatalogItem | null>(null);
  const [run, setRun] = useState<RunResult | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [busy, setBusy] = useState(false);

  const select = useCallback(async (item: CatalogItem, goTo: Tab = "card") => {
    setSelected(item);
    setBusy(true);
    try {
      const result = await api.runAssessment(item);
      setRun(result);
      setAudit(await api.getAudit(item.app_id));
      setTab(goTo);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    api.getCatalog().then((c) => {
      setCatalog(c);
      if (c.length) select(c[0]);
    });
  }, [select]);

  const onResume = async (decision: "approve" | "override" | "request_info", reason: string) => {
    if (!selected) return;
    const result = await api.resumeRun(selected.app_id, decision, reason);
    setRun(result);
    setAudit(await api.getAudit(selected.app_id));
  };

  if (!entered) return <Landing onEnter={() => setEntered(true)} />;

  return (
    <div className="relative z-10 min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-ivory/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 sm:px-10">
          <button onClick={() => setEntered(false)} className="transition-opacity hover:opacity-70" aria-label="Home">
            <Brand />
          </button>
          <div className="flex items-center gap-3">
            <span className="hidden font-mono text-[12px] text-ink-faint sm:inline">
              human-in-the-loop underwriting
            </span>
            <Chip tone="emerald">
              <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-current" />
              Synthetic · no PII
            </Chip>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 sm:px-10">
        {/* Applicant quick-switch — selecting runs the orchestrator live. */}
        <div className="flex flex-wrap items-center gap-2 pt-7">
          <span className="mr-1 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-faint">Applicant</span>
          {catalog.map((c) => {
            const active = selected?.app_id === c.app_id;
            return (
              <button
                key={c.app_id}
                onClick={() => select(c)}
                className={`rounded-full border px-3.5 py-1.5 text-[13px] transition ${
                  active
                    ? "border-ink bg-ink text-paper"
                    : "border-line-strong bg-paper text-ink-soft hover:border-ink/40 hover:text-ink"
                }`}
              >
                {c.name}
              </button>
            );
          })}
          {busy && (
            <span className="ml-1 inline-flex items-center gap-2 font-mono text-[12px] text-amber-deep">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-amber" />
              running agent…
            </span>
          )}
        </div>

        {/* Tab nav — an underlined index, not a pill tray. */}
        <nav className="mt-6 flex gap-7 border-b border-line">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`-mb-px border-b-2 pb-3 text-[14px] font-medium transition ${
                tab === t.id
                  ? "border-emerald text-ink"
                  : "border-transparent text-ink-faint hover:text-ink-soft"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      <main className="mx-auto max-w-6xl px-6 py-9 sm:px-10">
        {tab === "card" && run && <HealthCard score={run.score} name={selected?.name ?? ""} />}
        {tab === "console" && run && (
          <UnderwriterConsole run={run} name={selected?.name ?? ""} onResume={onResume} />
        )}
        {tab === "audit" && <AuditTrail events={audit} />}
        {tab === "catalog" && (
          <Catalog items={catalog} selectedId={selected?.app_id} archToneOf={(a) => ARCH_TONE[a]} onSelect={(c) => select(c)} />
        )}
        {!run && tab !== "catalog" && (
          <p className="font-mono text-[13px] text-ink-faint">Select an applicant to run the agent.</p>
        )}
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-10 sm:px-10">
        <p className="border-t border-line pt-5 font-mono text-[11px] text-ink-faint">
          CredSight · the LLM never computes the score — a deterministic, versioned model decides; the agent
          orchestrates, reconciles, and explains. All data synthetic.
        </p>
      </footer>
    </div>
  );
}
