// Applicant catalog — the demo MSMEs the orchestrator can run (GET /api/catalog).
// Selecting a row triggers a live agent run (App.select).

import type { CatalogItem } from "../types";
import { Card, Chip, SectionLabel } from "./ui";

type ArchTone = "azure" | "emerald" | "amber" | "rose";

export function Catalog({
  items,
  selectedId,
  onSelect,
  archToneOf,
}: {
  items: CatalogItem[];
  selectedId?: string;
  onSelect: (item: CatalogItem) => void;
  archToneOf: (a: CatalogItem["archetype"]) => ArchTone;
}) {
  return (
    <Card className="reveal px-7 py-7">
      <SectionLabel>Applicants</SectionLabel>
      <p className="-mt-1 mb-5 text-[14px] text-ink-soft">
        Select to run the agent: ingest → reconcile → score → human gate → action.
      </p>
      <ul className="divide-y divide-line">
        {items.map((c) => {
          const active = selectedId === c.app_id;
          return (
            <li key={c.app_id}>
              <button
                onClick={() => onSelect(c)}
                className={`group flex w-full items-center justify-between gap-4 py-4 text-left transition ${
                  active ? "" : "hover:translate-x-0.5"
                }`}
              >
                <div className="flex items-center gap-3.5">
                  <span
                    className={`h-2 w-2 rounded-full transition ${active ? "bg-emerald" : "bg-line-strong group-hover:bg-ink-faint"}`}
                  />
                  <div>
                    <div className={`font-display text-[18px] font-medium ${active ? "text-ink" : "text-ink"}`}>
                      {c.name}
                    </div>
                    <div className="font-mono text-[12px] text-ink-faint">
                      {c.sector} · {c.app_id}
                    </div>
                  </div>
                </div>
                <Chip tone={archToneOf(c.archetype)}>{c.archetype.replace(/_/g, " ")}</Chip>
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
