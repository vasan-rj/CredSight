# CredSight frontend

Demo UI for the golden path (see `../doc/prd.md` §15): **Health Card → Underwriter Console (HITL) → Audit Trail → Portfolio**.

Stack: Vite + React + TypeScript + Tailwind v4.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

Runs standalone today: `src/api.ts` returns mock data (`src/mock.ts`, Lakshmi is the golden-demo MSME). Flip `USE_MOCK = false` in `src/api.ts` once the backend exposes `/api` — Vite proxies `/api` → `http://localhost:8000` (the CredSight decisioning/orchestrator service).

`src/types.ts` mirrors the backend contracts (`src/credsight/scoring/schema.py`, `governance/audit.py`) — keep them in sync.

Layout:
- `components/HealthCard.tsx` — composite ring, 5 dimension gauges, confidence, SHAP strengths/risks (the hero).
- `components/UnderwriterConsole.tsx` — the HITL approval gate (the trust beat).
- `components/AuditTrail.tsx` — append-only event log.
- `components/Portfolio.tsx` — lender portfolio view.
