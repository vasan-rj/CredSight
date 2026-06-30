# TODOS

Design and UX debt tracked here. Each item is a deferral from a design review with full rationale.

---

## TODO-1: Create DESIGN.md
**What:** 1-page DESIGN.md in repo root codifying the Ledger design system.
**Why:** Prevents design drift as the codebase grows; canonical reference for contributors. Token semantics (amber=HITL, emerald=go/trust, rose=risk/refer, azure=consent), font stack (Fraunces/Hanken Grotesk/JetBrains Mono), spacing principles, component vocabulary.
**Pros:** Prevents silent drift; makes the design system explicit; speeds up new-contributor onboarding.
**Cons:** 10-minute write that isn't part of the demo. Defer until MVP core is running.
**Context:** Surfaced by /plan-design-review 2026-06-17. The system exists in index.css but isn't codified.
**Depends on:** Nothing.

---

## TODO-2: Contrast audit — `text-[11px] text-ink-faint` informational labels
**What:** Audit all `text-[11px] text-ink-faint` usage; replace with `text-ink-soft` where text carries information.
**Why:** WCAG 2.1 AA — #9c9384 on #f6f2e9 at 11px fails the 4.5:1 contrast requirement. Reserve `ink-faint` for decorative/separator uses only.
**Pros:** Accessibility compliance; clearer metadata at a glance.
**Cons:** ~15 minutes; low demo priority for a hackathon.
**Context:** Surfaced by /plan-design-review 2026-06-17. Files to check: all `frontend/src/components/*.tsx`.
**Depends on:** Nothing.

---

## TODO-3: Graph keyboard accessibility
**What:** Make the force-directed SVG graph keyboard-navigable. Add `tabIndex` on nodes, Enter/Space to expand/collapse, ARIA labels per node (`aria-label="PolicyClause: {title}"`), and a skip-link to the graph container.
**Why:** WCAG 2.1 AA for interactive SVG. Required for production accessibility; demo-grade for now.
**Pros:** Fully accessible knowledge graph; required for any bank customer deployment.
**Cons:** ~3 hours. The graph is demo-only at hackathon stage and not customer-facing yet.
**Context:** Surfaced by /plan-design-review 2026-06-17. File: `frontend/src/components/GraphView.tsx`.
**Depends on:** D11 (graph palette spec, T11) should be implemented first.

---

## TODO-4: E2E test stubs for 3 critical demo flows
**What:** Three E2E test stubs covering: (1) Lakshmi thin-file full demo arc (select → HITL pause → approve → audit shows events), (2) override-to-pattern arc (8 overrides in segment → recommendation surfaces), (3) capture-to-graph arc (capture note → run dream cycle → graph adds node).
**Why:** Unit tests cover individual functions but don't catch integration failures (audit path mismatch, store sync issues) found in the eng review. These 3 flows are the demo's winning beats — if any silently breaks, judges see a broken demo.
**Pros:** Catches integration regressions before a live demo run; fast to re-run.
**Cons:** Playwright setup overhead (~30min), needs a running backend; not standard pytest.
**Context:** Surfaced by /plan-eng-review 2026-06-18. Test plan artifact: `~/.gstack/projects/India_runs/vasan-master-eng-review-test-plan-20260618-130626.md`. No E2E framework in repo yet.
**Depends on:** T15-T24 backend fixes should land first so tests exercise the correct paths.

---

## TODO-5: `approve_recommendation` error handling for `var/model-versions.jsonl` write failure
**What:** Wrap the `var/model-versions.jsonl` append in `try/except IOError` with a logged warning. Return `{"ok": True, "rec_id": rec_id, "status": "approved", "version_recorded": False}` if the write fails.
**Why:** Silent failure leaves the version history timeline empty with no feedback to the underwriter. Currently if `var/` directory doesn't exist or is read-only, the approval succeeds in the audit log but the version history never updates.
**Pros:** Underwriter sees an explicit signal if version history fails; easier to debug in demo.
**Cons:** Minor; only matters if filesystem state is wrong.
**Context:** Surfaced by /plan-eng-review 2026-06-18. Depends on T17 (model-versions endpoint) being built first.
**Depends on:** T17.
