# Real-Data Integration — Task Plan

**Goal:** Replace the 4-archetype synthetic wall with three new data entry paths:
1. **CSV/JSON upload** — judges upload actual bank statement + GST CSVs, get a live score
2. **IDBI sandbox** — flip each connector to sandbox mode via config (no code change in agents)
3. **Expanded catalog** — 20+ synthetic MSMEs + optional free GSTIN profile lookup

> **NOT in scope:** Live AA protocol (Sahamati FIP/FIU needs registered FIU entity), real CIBIL/Experian (commercial license), real GSTN API (GSP license), real UPI rails, money movement.

---

## Architecture decision

Current flow:

```
Catalog (4 archetypes) → SyntheticConnector → generate.py bundle → CanonicalProfile → score
```

New flow adds two parallel ingestion paths:

```
Path A (unchanged):  archetype+seed → SyntheticConnector → CanonicalProfile → score
Path B (new):        uploaded CSVs  → UploadParser        → CanonicalProfile → score
Path C (config flip): IDBI creds    → SandboxConnector    → CanonicalProfile → score
```

All three paths converge at `CanonicalProfile` — scoring/reconciliation/HITL unchanged.
The upload path **skips the ingestion node** in the LangGraph graph and injects a
pre-built CanonicalProfile directly, entering at the `reconcile` node.

---

## Phase 1 — CSV/JSON Upload Path (highest demo value)

### U1 · Upload data models
**File:** `src/credsight/data/upload.py`

Define Pydantic upload models + CSV column mappings for the 3 most common bank formats.

```
BankStatementUpload:
  - rows: list of { date, amount, balance, narration } (parsed from CSV)
  - bank_format: "generic" | "sbi" | "hdfc" | "icici" | "axis"

GSTUpload:
  - returns: list of { period, turnover, filed_on_time, nil_filing }
  - can be JSON (GSTN portal export) or CSV

UPIUpload (optional, stretch):
  - txns: list of { date, amount, payer_vpa, is_reversal }
```

CSV column auto-detection: try known header patterns before falling back to generic.

---

### U2 · Bank CSV parser
**File:** `src/credsight/data/upload.py` (extends U1)

Parse CSV → `list[BankTxn]` + `BankAccount`.

Column mappings to support:
| Bank | Date col | Amount col | Balance col | Narration col |
|------|----------|------------|-------------|---------------|
| Generic | Date/date/DATE | Debit/Credit or Amount | Balance | Description/Narration |
| SBI | Txn Date | Debit/Credit | Balance | Description |
| HDFC | Date | Withdrawal Amt. / Deposit Amt. | Closing Balance | Narration |
| ICICI | Value Date | Withdrawal Amount (INR) / Deposit Amount (INR) | Balance (INR) | Transaction Remarks |
| Axis | Tran. Date | Debit / Credit | Balance | Particulars |

Logic:
- Inflows: positive `amount` (Credit columns or positive Amount rows)
- Outflows: negative `amount`
- Bounces: detect "BOUNCE", "RETURN", "RTGS RETURN" in narration
- Obligations: detect "EMI", "MANDATE", "NACH", "ECS" in narration
- `avg_monthly_balance` computed from balance column if present

---

### U3 · GST JSON/CSV parser
**File:** `src/credsight/data/upload.py`

Accept two formats:
1. **GSTN portal JSON export** — `{"data": [{"ret_prd": "042025", "sup_det": {"txval": ...}}]}`
2. **Simple CSV** — columns: `period,turnover,filed_on_time` (for manual entry)

Output: `list[GstReturn]`

Period normalisation: "042025" → "2025-04", "Apr-25" → "2025-04", etc.

---

### U4 · Canonical profile builder from upload
**File:** `src/credsight/data/upload.py`

```python
def build_canonical_from_upload(
    app_id: str,
    name: str,
    sector: str,
    bank_csv: str | None,
    gst_data: str | None,
    upi_csv: str | None = None,
    gstin: str | None = None,
) -> CanonicalProfile
```

- Creates synthetic consent artefact (scope = what was uploaded)
- Missing sources go into `missing_sources` → lower confidence, not failure
- Returns same `CanonicalProfile` shape as existing synthetic path

---

### U5 · Backend upload API
**File:** `src/credsight/api/app.py`

```
POST /api/upload/parse
  multipart body: app_id (str), name (str), sector (str),
                  bank_csv (file, optional), gst_json (file, optional), upi_csv (file, optional)
  returns: { app_id, preview: { months, sources_found, turnover_estimate } }

POST /api/upload/run
  body: { app_id } — runs the orchestrator on the pre-parsed canonical stored in var/canonical/
  returns: RunResult (same shape as /orchestrator/run)
```

New orchestrator entry: `start_assessment_from_canonical(app_id)` in `agents/run.py`:
- Reads `var/canonical/{app_id}.json`
- Invokes the graph starting from `reconcile_node` (skips `ingest_node`)
- Otherwise identical to existing flow

---

### U6 · Frontend upload UI
**File:** `frontend/src/components/UploadMSME.tsx` (new)

Two-step wizard:
1. **Step 1 — Profile**: Name, Sector (dropdown), GSTIN (optional)
2. **Step 2 — Files**: Drag-and-drop zones for Bank CSV, GST JSON, UPI CSV (all optional)
   - Each zone shows accepted format + download link to sample file
   - Preview after parse: "Found 14 months of bank data, 12 GST returns, 1 source missing"
3. **Step 3 — Score**: POST to `/api/upload/run` → standard RunResult → switch to Health Card tab

Wire into `App.tsx`: add "Upload MSME" button in the applicant selector bar (distinct from catalog items).

---

### U7 · Sample files for judges
**Directory:** `samples/`

Create 4 sample files judges can download and upload:

| File | Description |
|------|-------------|
| `samples/bank_statement_generic.csv` | Generic format, 12 months, ~clean |
| `samples/bank_statement_hdfc.csv` | HDFC format, 18 months, stressed pattern |
| `samples/gst_returns.json` | GSTN portal JSON export, 12 returns |
| `samples/gst_returns_simple.csv` | Simple CSV, 6 returns (thin-file test) |

Values are realistic but fully synthetic. Include README in the directory.

---

## Phase 2 — IDBI Sandbox Connectors (config-flip ready)

### S1 · Account Aggregator (AA) sandbox connector
**File:** `src/credsight/connectors/sandbox.py`

Implement `fetch()` for `system == "aa"`:
- Reads `IDBI_SANDBOX_BASE_URL` + `IDBI_SANDBOX_API_KEY` from config
- POST `/aa/consent` to create consent artefact
- GET `/aa/data/{consent_id}` to fetch consented data
- Map response → `{"accounts": [...], "txns": [...]}`  (same shape as synthetic bundle)
- Timeout: 10s, 2 retries with exponential backoff
- Missing/empty response → partial data (not an error), appended to `missing_sources`

---

### S2 · GST sandbox connector
**File:** `src/credsight/connectors/sandbox.py`

Implement `fetch()` for `system == "gst"`:
- GET `/gst/returns/{gstin}?from={from}&to={to}`
- Map GSTR-3B response → `{"returns": [...]}` shape
- Handle 404 (GSTIN not found) as empty returns → `missing_sources`

---

### S3 · UPI, EPFO, Bureau sandbox connectors
**File:** `src/credsight/connectors/sandbox.py`

Stub `fetch()` for UPI, EPFO, Bureau:
- UPI: GET `/upi/txns/{vpa}?from={from}&to={to}`
- EPFO: GET `/epfo/establishment/{id}`
- Bureau: GET `/bureau/report/{pan}`
- Each raises `NotImplementedError("IDBI sandbox endpoint not confirmed")` with a clear message
  until the actual sandbox endpoint is confirmed post-hackathon

---

### S4 · Sandbox env template
**File:** `.env.sandbox.example`

```
CREDSIGHT_ADAPTER_AA=sandbox
CREDSIGHT_ADAPTER_GST=sandbox
CREDSIGHT_ADAPTER_UPI=synthetic
CREDSIGHT_ADAPTER_EPFO=synthetic
CREDSIGHT_ADAPTER_BUREAU=synthetic
IDBI_SANDBOX_BASE_URL=https://sandbox.idbi.co.in/api/v1
IDBI_SANDBOX_API_KEY=your-api-key-here
CREDSIGHT_HITL_AMOUNT_THRESHOLD=600000
```

Comment each line with what it controls.

---

### S5 · Sandbox smoke test
**File:** `tests/test_sandbox_connectors.py`

- Test `_SandboxConnector.fetch()` raises `NotImplementedError` for unimplemented sources (expected)
- Test AA + GST connectors with `respx` mock — mock the HTTP endpoints, assert correct mapping
- Test partial response (missing bank account) lands in `missing_sources`, not exception
- Mark tests `@pytest.mark.sandbox` so they run only with `pytest -m sandbox`

---

## Phase 3 — Expanded Catalog

### C1 · 20+ synthetic MSMEs
**File:** `src/credsight/service/demo_seed.py`

Current: 4 fixed seeds (Lakshmi, Sri Auto, Anand Tailors, Deccan Traders).
Add 16 more across sectors and archetypes:

| Count | Archetype | Sectors |
|-------|-----------|---------|
| 5 | thin_file | Kirana, Street food, Tailoring, Cobbler, Flower vendor |
| 4 | strong | IT services, Pharma retail, Auto dealer, Dairy |
| 4 | stressed | Restaurant, Textile, Construction labour, Handicrafts |
| 3 | fraud | Used goods trader, Cash-heavy wholesale, Import agent |

Each has a unique name, realistic sector, and distinct seed. Portfolio view shows real diversity.

---

### C2 · GSTIN public lookup (free, no auth)
**File:** `src/credsight/data/gstin_lookup.py`

Use the public GSTN verification endpoint (no API key, rate-limited):
```
GET https://cleartax.in/f/gstin/{gstin}
   OR
GET https://apisetu.gov.in/gstn/gstin/{gstin}
```

Returns: legal name, registration date, state, business type (Proprietorship/Partnership/etc.)

Wire into the upload flow: if GSTIN is provided, pre-fill Name + sector from GSTN lookup.
Fail silently (empty lookup → user enters manually).

NOT a scoring input — only for profile pre-fill.

---

## Task priority / order

```
Week 1 (now):    U1 → U2 → U3 → U4 → U5 → U6 → U7
Week 2 (after):  S1 → S2 → S3 → S4 → S5
When time:       C1 → C2
```

U5 (backend API) depends on U1-U4. U6 (frontend) depends on U5.
S-series are independent. C1 is independent. C2 depends on U5 (upload form reuses the GSTIN lookup).

---

## Files to create / modify

| File | Action | Tasks |
|------|--------|-------|
| `src/credsight/data/upload.py` | CREATE | U1–U4 |
| `src/credsight/api/app.py` | MODIFY (add endpoints) | U5 |
| `src/credsight/api/schemas.py` | MODIFY (add UploadIn) | U5 |
| `src/credsight/agents/run.py` | MODIFY (add `start_assessment_from_canonical`) | U5 |
| `src/credsight/agents/graph.py` | MODIFY (new entry node `from_canonical`) | U5 |
| `frontend/src/components/UploadMSME.tsx` | CREATE | U6 |
| `frontend/src/api.ts` | MODIFY (add upload API calls) | U6 |
| `frontend/src/types.ts` | MODIFY (add UploadPreview type) | U6 |
| `frontend/src/App.tsx` | MODIFY (Upload button + state) | U6 |
| `samples/` | CREATE (4 sample files + README) | U7 |
| `src/credsight/connectors/sandbox.py` | MODIFY (implement HTTP calls) | S1–S3 |
| `.env.sandbox.example` | CREATE | S4 |
| `tests/test_sandbox_connectors.py` | CREATE | S5 |
| `src/credsight/service/demo_seed.py` | MODIFY (20 seeds) | C1 |
| `src/credsight/data/gstin_lookup.py` | CREATE | C2 |

---

## What stays unchanged

- All scoring, reconciliation, HITL logic — untouched
- `CanonicalProfile` schema — unchanged (the convergence point)
- Agent graph — only a new entry node added, existing nodes unchanged
- Mock data in `frontend/src/mock.ts` — remains for `USE_MOCK=true` mode
- Existing 4 catalog archetypes — still present, upload is additive

---

## Demo narrative with real data

**Judge flow:**
1. Go to demo → see 4 catalog archetypes (synthetic, reliable)
2. Click "Upload MSME" → drag in `samples/bank_statement_hdfc.csv` + `samples/gst_returns.json`
3. System scores it live — different result from any archetype
4. HITL gate fires if confidence is low → underwriter decision
5. "The same pipeline that scores the synthetic Lakshmi just scored data you uploaded yourself"

This beats pure synthetic because the judges can **verify** the system isn't hardcoded.
