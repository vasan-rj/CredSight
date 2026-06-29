// GBrain — knowledge graph tab. Force-directed SVG view + organize trigger + stats.

import { useEffect, useState } from "react";
import { GraphView, type GEdge, type GNode } from "./GraphView";

interface GraphSummary {
  clauses: number;
  edges: number;
  communities: number;
  community_detail: Record<string, string[]>;
  dedup_candidates: number;
  dedup_pairs: [string, string][];
  built_at: string | null;
  // from the persisted graph.json (graph view)
  nodes?: { ref: string; title: string; source: string }[];
  edge_list?: GEdge[];
}

async function fetchGraph(): Promise<GraphSummary> {
  const res = await fetch("/api/knowledge/graph");
  if (!res.ok) throw new Error(`/api/knowledge/graph → ${res.status}`);
  const raw = await res.json();
  // backend returns: { clauses, edges(count), communities, community_detail,
  //   dedup_candidates, dedup_pairs, built_at, nodes[], edges[] (from save_graph) }
  // Map array field names carefully — the organize summary uses 'edges' as a count,
  // but the persisted graph.json (load_graph) has 'nodes' + 'edges' arrays.
  // The API currently calls organize() which returns the summary dict. We extend
  // it to also include nodes/edges arrays via the persisted file.
  return {
    ...raw,
    edge_list: raw.edge_list ?? [],
  };
}

async function runOrganize(): Promise<GraphSummary> {
  const res = await fetch("/api/knowledge/organize", { method: "POST" });
  if (!res.ok) throw new Error(`/api/knowledge/organize → ${res.status}`);
  const raw = await res.json();
  return { ...raw, edge_list: raw.edge_list ?? [] };
}

function StatBox({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg border border-line bg-paper px-5 py-4">
      <p className="font-mono text-[28px] font-bold text-ink">{value ?? "—"}</p>
      <p className="mt-0.5 font-mono text-[11px] text-ink-faint">{label}</p>
    </div>
  );
}

const ORGANIZE_STEPS = [
  "Loading policy clauses…",
  "Computing Jaccard similarity over term bags…",
  "Building edge graph (threshold ≥ 0.06)…",
  "Detecting communities (connected components)…",
  "Flagging dedup candidates (threshold ≥ 0.45)…",
  "Saving graph to var/knowledge/graph.json…",
  "Dream cycle complete.",
];

export function GBrain() {
  const [graph, setGraph]   = useState<GraphSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [organizeLog, setOrganizeLog] = useState<string[]>([]);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    fetchGraph()
      .then(setGraph)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const organize = async () => {
    setRunning(true);
    setOrganizeLog([]);
    setError(null);

    // Simulate progress log while the synchronous POST runs.
    const timers: ReturnType<typeof setTimeout>[] = [];
    ORGANIZE_STEPS.forEach((step, i) => {
      timers.push(setTimeout(() => {
        setOrganizeLog(prev => [...prev, step]);
      }, i * 300));
    });

    try { setGraph(await runOrganize()); }
    catch (e) { setError((e as Error).message); }
    finally {
      timers.forEach(clearTimeout);
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 font-mono text-[13px] text-ink-faint">
        <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-azure" />
        Loading knowledge graph…
      </div>
    );
  }

  // Build typed node/edge arrays for GraphView.
  // The API's organize() returns community_detail (hub→refs) — extract node list from it.
  const gNodes: GNode[] = graph
    ? Object.values(graph.community_detail ?? {})
        .flat()
        .map(ref => {
          const src = ref.split("#")[0] ?? "unknown";
          const node = graph.nodes?.find(n => n.ref === ref);
          return { id: ref, title: node?.title ?? ref.split("#")[1]?.replace(/-/g, " ") ?? ref, source: src };
        })
    : [];

  // edges: use edge_list if present, else build stub edges from dedup pairs
  const gEdges: GEdge[] = graph?.edge_list?.length
    ? graph.edge_list
    : (graph?.dedup_pairs ?? []).map(([a, b]) => ({
        source: a, target: b, weight: 0.5, reason: "dedup_candidate",
      }));

  const communities = graph?.community_detail ?? {};

  return (
    <div className="space-y-7">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[18px] font-semibold text-ink">Knowledge Graph</h2>
          <p className="mt-0.5 font-mono text-[12px] text-ink-faint">
            {graph?.built_at
              ? `Last built ${new Date(graph.built_at).toLocaleString()}`
              : "Graph not built — click Organize to run the dream cycle"}
          </p>
        </div>
        <button
          onClick={organize}
          disabled={running}
          className="shrink-0 rounded-lg border border-azure px-4 py-2 font-mono text-[12px] font-semibold text-azure transition hover:bg-azure/10 disabled:opacity-50"
        >
          {running ? "organizing…" : "Organize"}
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 font-mono text-[12px] text-rose-600">
          {error}
        </p>
      )}

      {/* Organize progress log */}
      {organizeLog.length > 0 && (
        <div className="rounded-lg border border-azure/30 bg-azure-soft px-4 py-3 space-y-1">
          {organizeLog.map((line, i) => (
            <p key={i} className="font-mono text-[12px] text-azure">
              <span className="mr-2 text-azure/50">›</span>{line}
            </p>
          ))}
        </div>
      )}

      {/* Graph View */}
      {gNodes.length > 0 ? (
        <GraphView nodes={gNodes} edges={gEdges} communities={communities} />
      ) : (
        <div className="flex h-64 items-center justify-center rounded-xl border border-line bg-paper">
          <p className="font-mono text-[13px] text-ink-faint">
            Click <span className="text-azure">Organize</span> to build the clause graph.
          </p>
        </div>
      )}

      {/* Stats row */}
      {graph && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatBox label="policy clauses" value={graph.clauses} />
          <StatBox label="cross-clause links" value={graph.edges} />
          <StatBox label="topic communities" value={graph.communities} />
          <StatBox label="dedup candidates" value={graph.dedup_candidates} />
        </div>
      )}

      {/* Communities compact list */}
      {graph && Object.keys(communities).length > 0 && (
        <div>
          <h3 className="mb-3 text-[15px] font-semibold text-ink">Communities</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(communities).map(([hub, refs]) => (
              <div key={hub} className="rounded-lg border border-line bg-paper px-4 py-3">
                <p className="mb-1.5 font-mono text-[11px] font-semibold text-ink truncate" title={hub}>
                  {hub.split("#")[1]?.replace(/-/g, " ") ?? hub}
                  <span className="ml-1.5 text-ink-faint">({refs.length})</span>
                </p>
                <ul className="space-y-0.5">
                  {refs.slice(0, 5).map(ref => (
                    <li key={ref} className="truncate font-mono text-[10px] text-ink-faint" title={ref}>
                      {ref.split("#")[1]?.replace(/-/g, " ") ?? ref}
                    </li>
                  ))}
                  {refs.length > 5 && (
                    <li className="font-mono text-[10px] text-ink-faint">+{refs.length - 5} more…</li>
                  )}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dedup candidates */}
      {graph?.dedup_pairs?.length ? (
        <div>
          <h3 className="mb-3 text-[15px] font-semibold text-ink">
            Dedup Candidates
            <span className="ml-2 rounded-full bg-amber/20 px-2 py-0.5 font-mono text-[11px] text-amber-deep">
              {graph.dedup_pairs.length}
            </span>
          </h3>
          <div className="space-y-2">
            {graph.dedup_pairs.map(([a, b], i) => (
              <div key={i} className="flex items-center gap-2 rounded-lg border border-amber/30 bg-amber/5 px-4 py-2">
                <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-ink" title={a}>{a}</span>
                <span className="shrink-0 text-ink-faint">↔</span>
                <span className="min-w-0 flex-1 truncate text-right font-mono text-[11px] text-ink" title={b}>{b}</span>
              </div>
            ))}
          </div>
          <p className="mt-2 font-mono text-[11px] text-ink-faint">
            High-similarity cross-doc pairs. Flagged for human review — not auto-merged.
          </p>
        </div>
      ) : null}

      <p className="border-t border-line pt-4 font-mono text-[11px] text-ink-faint">
        Clause graph: Jaccard similarity over term bags · edges ≥ 0.06 · dedup ≥ 0.45 ·
        communities = connected components · hub node = highest degree in cluster.
      </p>
    </div>
  );
}
