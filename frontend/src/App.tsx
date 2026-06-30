// Demo shell — drives a LIVE orchestrator run. Landing → pick an applicant → the
// agent runs ingest → reconcile → score → HITL gate → action; the tabs show the
// golden path (Health Card, Underwriter Console, Audit Trail) for the selected run.

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { HealthCard, HealthCardSkeleton } from "./components/HealthCard";
import { PathToBankability } from "./components/PathToBankability";
import { UnderwriterConsole } from "./components/UnderwriterConsole";
import { AuditTrail } from "./components/AuditTrail";
import { Catalog } from "./components/Portfolio";
import { Landing } from "./components/Landing";
import { Brand } from "./components/Brand";
import { LearningLoop } from "./components/LearningLoop";
import { GBrain } from "./components/GBrain";
import { NeedsCard } from "./components/NeedsCard";
import { UploadMSME } from "./components/UploadMSME";
import { Chip } from "./components/ui";
import type { AuditEvent, CatalogItem, RunResult } from "./types";

type Tab = "card" | "console" | "audit" | "catalog" | "learning" | "knowledge";

const TABS: { id: Tab; label: string }[] = [
  { id: "catalog", label: "Applicants" },
  { id: "card", label: "Health Card" },
  { id: "console", label: "Underwriter Console" },
  { id: "audit", label: "Audit Trail" },
  { id: "learning", label: "Learning Loop" },
  { id: "knowledge", label: "Knowledge Graph" },
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
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);

  const select = useCallback(async (item: CatalogItem, goTo: Tab = "card") => {
    setSelected(item);
    setBusy(true);
    setError(null);
    try {
      const result = await api.runAssessment(item);
      setRun(result);
      setAudit(await api.getAudit(item.app_id));
      setTab(goTo);
    } catch (e) {
      setError((e as Error).message);
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

  // T1: Auto-switch to the Underwriter Console when the agent pauses for a human.
  useEffect(() => {
    if (run?.status === "pending_human" && tab !== "console") {
      const t = setTimeout(() => setTab("console"), 400);
      return () => clearTimeout(t);
    }
  }, [run?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const onResume = async (decision: "approve" | "override" | "request_info", reason: string) => {
    if (!selected || !run) return;
    const result = await api.resumeRun(selected.app_id, decision, reason, run);
    setRun(result);
    setAudit(await api.getAudit(selected.app_id));
  };

  const onUploadDone = (result: RunResult, uploadedName: string) => {
    setRun(result);
    setSelected({ app_id: result.app_id, name: uploadedName, archetype: "thin_file", seed: 0, sector: "" });
    setAudit([]);
    setShowUpload(false);
    setTab("card");
    api.getAudit(result.app_id).then(setAudit).catch(() => {});
  };

  if (!entered) return <Landing onEnter={() => setEntered(true)} />;

  return (
    <div className="relative z-10 min-h-screen">
      {showUpload && <UploadMSME onDone={onUploadDone} onClose={() => setShowUpload(false)} />}
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
          <button
            onClick={() => setShowUpload(true)}
            className="rounded-full border border-azure/50 bg-azure-soft px-3.5 py-1.5 text-[13px] text-azure-deep transition hover:border-azure/80"
          >
            + Upload MSME
          </button>
          {busy && (
            <span className="ml-1 inline-flex items-center gap-2 font-mono text-[12px] text-amber-deep">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-amber" />
              running agent…
            </span>
          )}
        </div>

        {/* Tab nav — scrollable on mobile, underlined index on desktop. */}
        <div className="relative mt-6">
          <nav className="flex gap-7 overflow-x-auto scrollbar-hide border-b border-line">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`relative -mb-px shrink-0 min-h-[44px] border-b-2 pb-3 text-[14px] font-medium transition ${
                  tab === t.id
                    ? "border-emerald text-ink"
                    : "border-transparent text-ink-faint hover:text-ink-soft"
                }`}
              >
                {t.label}
                {t.id === "console" && run?.status === "pending_human" && (
                  <span className="ml-1.5 inline-flex h-2 w-2 rounded-full bg-amber align-middle" />
                )}
              </button>
            ))}
          </nav>
          {/* right-fade gradient hint for scrollable tabs on narrow screens */}
          <div className="pointer-events-none absolute right-0 top-0 h-full w-10 bg-gradient-to-l from-ivory to-transparent" />
        </div>
      </div>

      <main className="mx-auto max-w-6xl px-6 py-9 sm:px-10">
        {error && (
          <div className="mb-6 rounded-xl border border-rose/30 bg-rose-soft px-5 py-4 font-mono text-[13px] text-rose-deep">
            Agent error: {error}
          </div>
        )}
        {tab === "card" && (
          busy
            ? <HealthCardSkeleton />
            : run
              ? <>
                  {run.needs && run.product_matches && (
                    <div className="mb-6">
                      <NeedsCard needs={run.needs} productMatches={run.product_matches} />
                    </div>
                  )}
                  <HealthCard score={run.score} name={selected?.name ?? ""} pathway={run.pathway} />
                  {run.pathway && <PathToBankability pathway={run.pathway} />}
                </>
              : <p className="font-mono text-[13px] text-ink-faint">Select an applicant to run the agent.</p>
        )}
        {tab === "console" && run && (
          <UnderwriterConsole run={run} name={selected?.name ?? ""} onResume={onResume} />
        )}
        {tab === "audit" && <AuditTrail events={audit} />}
        {tab === "catalog" && (
          <Catalog items={catalog} selectedId={selected?.app_id} archToneOf={(a) => ARCH_TONE[a]} onSelect={(c) => select(c)} />
        )}
        {tab === "learning" && <LearningLoop />}
        {tab === "knowledge" && <GBrain />}
        {!run && !busy && tab !== "catalog" && tab !== "learning" && tab !== "knowledge" && tab !== "card" && (
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
