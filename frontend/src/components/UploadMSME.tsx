// Upload wizard — judges drag in their own CSV/JSON files and get a live score.
// Step 1: profile (name, sector, GSTIN)
// Step 2: files (bank CSV, GST JSON/CSV, UPI CSV — all optional individually)
// Step 3: score (calls /api/upload/parse then /api/upload/run)
// On success: calls onDone(RunResult) → App sets run state, switches to Health Card tab.

import { useRef, useState } from "react";
import { api } from "../api";
import type { RunResult, UploadPreview } from "../types";

const SECTORS = [
  "Kirana / retail",
  "Micro-manufacturing",
  "Services",
  "Wholesale",
  "Food & beverages",
  "Textile / apparel",
  "Auto repair / parts",
  "Healthcare",
  "Construction",
  "IT services",
  "Agriculture / dairy",
  "Handicrafts",
  "Other",
];

interface Props {
  onDone: (result: RunResult, name: string) => void;
  onClose: () => void;
}

type Step = "profile" | "files" | "scoring";

function FileZone({
  label, hint, accept, file, onChange, sampleHref, sampleName,
}: {
  label: string; hint: string; accept: string;
  file: File | null; onChange: (f: File | null) => void;
  sampleHref: string; sampleName: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="rounded-xl border border-line bg-paper p-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-ink">{label}</span>
        <a
          href={sampleHref}
          download={sampleName}
          className="font-mono text-[11px] text-azure-deep underline-offset-2 hover:underline"
        >
          sample ↓
        </a>
      </div>
      <p className="mt-0.5 font-mono text-[11px] text-ink-faint">{hint}</p>
      <div
        className={`mt-3 flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed px-4 py-6 transition ${
          file ? "border-emerald/60 bg-emerald-soft" : "border-line-strong hover:border-ink/40"
        }`}
        onClick={() => ref.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) onChange(f);
        }}
      >
        <input
          ref={ref}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <div className="flex items-center gap-2">
            <span className="font-mono text-[12px] text-emerald-deep">{file.name}</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onChange(null); }}
              className="rounded-full p-0.5 text-ink-faint hover:text-rose"
            >
              ✕
            </button>
          </div>
        ) : (
          <span className="font-mono text-[12px] text-ink-faint">
            drag & drop or click to choose
          </span>
        )}
      </div>
    </div>
  );
}

function PreviewBadge({ preview }: { preview: UploadPreview }) {
  const miss = preview.missing_sources;
  return (
    <div className="rounded-xl border border-emerald/30 bg-emerald-soft p-4">
      <p className="text-[13px] font-medium text-emerald-deep">Parsed successfully</p>
      <ul className="mt-2 space-y-1 font-mono text-[12px] text-ink-soft">
        {preview.months_bank > 0 && (
          <li>Bank: {preview.months_bank} month{preview.months_bank !== 1 ? "s" : ""} of statements</li>
        )}
        {preview.months_gst > 0 && (
          <li>GST: {preview.months_gst} return{preview.months_gst !== 1 ? "s" : ""}</li>
        )}
        {preview.upi_txn_count > 0 && (
          <li>UPI: {preview.upi_txn_count} transactions</li>
        )}
        {preview.turnover_estimate != null && (
          <li>Avg monthly turnover: ₹{Math.round(preview.turnover_estimate).toLocaleString("en-IN")}</li>
        )}
        {miss.length > 0 && (
          <li className="text-amber-deep">
            Missing (lower confidence): {miss.join(", ")}
          </li>
        )}
      </ul>
    </div>
  );
}

export function UploadMSME({ onDone, onClose }: Props) {
  const [step, setStep] = useState<Step>("profile");

  // Profile fields
  const [name, setName]     = useState("");
  const [sector, setSector] = useState(SECTORS[0]);
  const [gstin, setGstin]   = useState("");

  // Files
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [gstFile,  setGstFile]  = useState<File | null>(null);
  const [upiFile,  setUpiFile]  = useState<File | null>(null);

  // State
  const [preview, setPreview]   = useState<UploadPreview | null>(null);
  const [appId,         setAppId]         = useState("");
  const [busy,          setBusy]          = useState(false);
  const [error,         setError]         = useState<string | null>(null);
  const [gstinFilling,  setGstinFilling]  = useState(false);

  const profileValid = name.trim().length >= 2;

  async function handleParse() {
    if (!bankFile && !gstFile && !upiFile) {
      setError("Upload at least one file (bank CSV or GST data) to continue.");
      return;
    }
    setBusy(true);
    setError(null);
    const id = `UPLOAD-${Date.now()}`;
    setAppId(id);
    try {
      const { preview: pv } = await api.parseUpload(
        id, name.trim(), sector, bankFile, gstFile, upiFile, gstin.trim() || undefined,
      );
      setPreview(pv);
      setStep("scoring");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleScore() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.runUpload(appId, name.trim());
      onDone(result, name.trim());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-2xl border border-line bg-ivory p-8 shadow-xl mx-4">
        <button
          onClick={onClose}
          className="absolute right-5 top-5 rounded-full p-1.5 text-ink-faint hover:text-ink"
        >
          ✕
        </button>

        <h2 className="text-[18px] font-semibold text-ink">Score your own MSME data</h2>
        <p className="mt-1 font-mono text-[12px] text-ink-faint">
          Upload real files — the same pipeline runs. No PII stored.
        </p>

        {/* Step indicator */}
        <div className="mt-4 flex items-center gap-2 font-mono text-[11px]">
          {(["profile", "files", "scoring"] as Step[]).map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 ${
                step === s ? "bg-ink text-paper"
                : i < ["profile","files","scoring"].indexOf(step) ? "bg-line text-ink-soft" : "text-ink-faint"
              }`}>
                {i + 1}
              </span>
              <span className={step === s ? "text-ink" : "text-ink-faint"}>
                {s === "profile" ? "Profile" : s === "files" ? "Files" : "Score"}
              </span>
              {i < 2 && <span className="text-line-strong">—</span>}
            </span>
          ))}
        </div>

        <div className="mt-5 space-y-4">
          {/* ── Step 1: Profile ─────────────────────────────────────────────── */}
          {step === "profile" && (
            <>
              <div>
                <label className="block text-[12px] font-medium text-ink-soft">Business name *</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Meera Textiles"
                  className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 text-[14px] text-ink outline-none focus:border-ink/60"
                />
              </div>
              <div>
                <label className="block text-[12px] font-medium text-ink-soft">Sector *</label>
                <select
                  value={sector}
                  onChange={(e) => setSector(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 text-[14px] text-ink outline-none focus:border-ink/60"
                >
                  {SECTORS.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[12px] font-medium text-ink-soft">
                  GSTIN <span className="text-ink-faint">(optional — auto-fills from GSTN)</span>
                </label>
                <input
                  value={gstin}
                  onChange={(e) => setGstin(e.target.value.toUpperCase())}
                  onBlur={async (e) => {
                    const g = e.target.value.trim();
                    if (g.length !== 15) return;
                    setGstinFilling(true);
                    try {
                      const info = await api.lookupGstin(g);
                      if (info.legal_name && !name) setName(info.trade_name || info.legal_name);
                    } catch { /* silent */ }
                    finally { setGstinFilling(false); }
                  }}
                  placeholder="29AAAAA0000A1Z5"
                  maxLength={15}
                  className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 font-mono text-[13px] text-ink outline-none focus:border-ink/60"
                />
                {gstinFilling && (
                  <span className="mt-1 block font-mono text-[11px] text-ink-faint">Looking up GSTN…</span>
                )}
              </div>
              <button
                onClick={() => setStep("files")}
                disabled={!profileValid}
                className="w-full rounded-xl bg-ink px-4 py-2.5 text-[14px] font-medium text-paper transition hover:bg-ink/80 disabled:opacity-40"
              >
                Continue →
              </button>
            </>
          )}

          {/* ── Step 2: Files ────────────────────────────────────────────────── */}
          {step === "files" && (
            <>
              <FileZone
                label="Bank statement CSV"
                hint="Generic, SBI, HDFC, ICICI, or Axis Bank format"
                accept=".csv,text/csv"
                file={bankFile}
                onChange={setBankFile}
                sampleHref="/samples/bank_statement_hdfc.csv"
                sampleName="bank_statement_hdfc.csv"
              />
              <FileZone
                label="GST returns"
                hint="GSTN portal JSON export or simple period,turnover,filed CSV"
                accept=".json,.csv,text/csv,application/json"
                file={gstFile}
                onChange={setGstFile}
                sampleHref="/samples/gst_returns.json"
                sampleName="gst_returns.json"
              />
              <FileZone
                label="UPI transactions (optional)"
                hint="date, amount, payer_vpa CSV"
                accept=".csv,text/csv"
                file={upiFile}
                onChange={setUpiFile}
                sampleHref="/samples/bank_statement_generic.csv"
                sampleName="upi_txns_sample.csv"
              />
              {error && (
                <p className="rounded-lg border border-rose/30 bg-rose-soft px-3 py-2 font-mono text-[12px] text-rose-deep">
                  {error}
                </p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => setStep("profile")}
                  className="flex-1 rounded-xl border border-line px-4 py-2.5 text-[14px] text-ink-soft transition hover:text-ink"
                >
                  ← Back
                </button>
                <button
                  onClick={handleParse}
                  disabled={busy}
                  className="flex-[2] rounded-xl bg-ink px-4 py-2.5 text-[14px] font-medium text-paper transition hover:bg-ink/80 disabled:opacity-50"
                >
                  {busy ? "Parsing…" : "Parse files →"}
                </button>
              </div>
            </>
          )}

          {/* ── Step 3: Score ─────────────────────────────────────────────────── */}
          {step === "scoring" && preview && (
            <>
              <PreviewBadge preview={preview} />
              <div className="rounded-xl border border-amber/30 bg-amber-soft px-4 py-3 font-mono text-[12px] text-amber-deep">
                The same ingest → reconcile → score → HITL pipeline runs on your data.
                HITL gate may fire if confidence is low.
              </div>
              {error && (
                <p className="rounded-lg border border-rose/30 bg-rose-soft px-3 py-2 font-mono text-[12px] text-rose-deep">
                  {error}
                </p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => { setStep("files"); setPreview(null); }}
                  className="flex-1 rounded-xl border border-line px-4 py-2.5 text-[14px] text-ink-soft transition hover:text-ink"
                >
                  ← Change files
                </button>
                <button
                  onClick={handleScore}
                  disabled={busy}
                  className="flex-[2] rounded-xl bg-emerald px-4 py-2.5 text-[14px] font-medium text-paper transition hover:bg-emerald/90 disabled:opacity-50"
                >
                  {busy ? "Scoring…" : "Score this MSME →"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
