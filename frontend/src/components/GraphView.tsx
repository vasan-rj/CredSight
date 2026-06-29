/**
 * Force-directed knowledge graph — pure SVG, zero extra dependencies.
 *
 * Physics: Fruchterman-Reingold-style simulation.
 *   • Repulsion: every node pair pushes apart (inverse-square).
 *   • Springs:   each edge pulls connected nodes toward an ideal distance.
 *   • Gravity:   weak pull toward canvas centre prevents drift.
 * Interactivity: drag nodes, pan canvas (drag background), zoom (scroll wheel).
 * Stops automatically when kinetic energy drops below threshold.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── types ─────────────────────────────────────────────────────────────────────

export interface GNode { id: string; title: string; source: string }
export interface GEdge { source: string; target: string; weight: number; reason: string }

interface Props {
  nodes: GNode[];
  edges: GEdge[];
  communities: Record<string, string[]>;   // hub-ref → member-refs[]
  width?: number;
  height?: number;
}

// ── colours (Ledger design system tokens) ───────────────────────────────────
// Policy sources: paper canvas + ink stroke (neutral, content-first).
// Agent learnings: azure-soft + azure (consent / knowledge provenance).

const SOURCE_PALETTE: Record<string, { fill: string; stroke: string; label: string }> = {
  "working-capital-eligibility": { fill: "#fdfbf5", stroke: "#1a160f", label: "Eligibility" },
  "fraud-and-consent":           { fill: "#fdfbf5", stroke: "#1a160f", label: "Fraud / Consent" },
  "thin-file-ntc":               { fill: "#fdfbf5", stroke: "#1a160f", label: "Thin-file / NTC" },
  "captured-learnings":          { fill: "#e4ebf0", stroke: "#355e7a", label: "Agent learnings" },
};
const DEFAULT_COLOR = { fill: "#fdfbf5", stroke: "#1a160f", label: "Policy" };

// Community cycle: emerald → amber → rose → azure (Ledger trust palette).
const COMMUNITY_CYCLE = ["#1f6b4a", "#bf7327", "#b0392b", "#355e7a"];

function palette(source: string) {
  for (const [k, v] of Object.entries(SOURCE_PALETTE)) {
    if (source.includes(k)) return v;
  }
  return DEFAULT_COLOR;
}

// Map community hubs to a stable cycle color index.
function communityColor(hubIndex: number): string {
  return COMMUNITY_CYCLE[hubIndex % COMMUNITY_CYCLE.length];
}

// ── physics constants ────────────────────────────────────────────────────────

const REPEL      = 4000;    // repulsion strength
const SPRING_K   = 0.035;   // spring stiffness
const SPRING_LEN = 130;     // ideal edge length px
const GRAVITY    = 0.003;   // centre-pull
const DAMPING    = 0.80;
const STOP_E     = 0.05;    // energy threshold to stop sim
const MAX_ITER   = 500;

// ── simulation node (mutable, lives in a ref) ────────────────────────────────

interface SNode {
  id: string; title: string; source: string;
  x: number; y: number; vx: number; vy: number;
  deg: number;
}

function buildSim(nodes: GNode[], edges: GEdge[], W: number, H: number): SNode[] {
  const deg: Record<string, number> = {};
  edges.forEach(e => { deg[e.source] = (deg[e.source] ?? 0) + 1; deg[e.target] = (deg[e.target] ?? 0) + 1; });
  return nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    const r = Math.min(W, H) * 0.28;
    return { id: n.id, title: n.title, source: n.source,
             x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle),
             vx: 0, vy: 0, deg: deg[n.id] ?? 0 };
  });
}

function step(sim: SNode[], edges: GEdge[], W: number, H: number): number {
  const cx = W / 2, cy = H / 2;
  const idx: Record<string, number> = {};
  sim.forEach((n, i) => { idx[n.id] = i; });

  // repulsion
  for (let i = 0; i < sim.length; i++) {
    for (let j = i + 1; j < sim.length; j++) {
      const dx = sim[j].x - sim[i].x, dy = sim[j].y - sim[i].y;
      const d2 = dx * dx + dy * dy, d = Math.max(Math.sqrt(d2), 1);
      const f = REPEL / d2, fx = f * dx / d, fy = f * dy / d;
      sim[i].vx -= fx; sim[i].vy -= fy;
      sim[j].vx += fx; sim[j].vy += fy;
    }
  }

  // springs
  for (const e of edges) {
    const si = idx[e.source], ti = idx[e.target];
    if (si == null || ti == null) continue;
    const dx = sim[ti].x - sim[si].x, dy = sim[ti].y - sim[si].y;
    const d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
    const stretch = (d - SPRING_LEN) * SPRING_K * (0.5 + e.weight);
    const fx = stretch * dx / d, fy = stretch * dy / d;
    sim[si].vx += fx; sim[si].vy += fy;
    sim[ti].vx -= fx; sim[ti].vy -= fy;
  }

  // gravity + damping + integrate
  let energy = 0;
  for (const n of sim) {
    n.vx += (cx - n.x) * GRAVITY; n.vy += (cy - n.y) * GRAVITY;
    n.vx *= DAMPING;               n.vy *= DAMPING;
    n.x  += n.vx;                  n.y  += n.vy;
    n.x   = Math.max(28, Math.min(W - 28, n.x));
    n.y   = Math.max(28, Math.min(H - 28, n.y));
    energy += n.vx * n.vx + n.vy * n.vy;
  }
  return energy;
}

// ── component ─────────────────────────────────────────────────────────────────

interface Tooltip { text: string; x: number; y: number }

export function GraphView({ nodes, edges, communities, width = 780, height = 460 }: Props) {
  const simRef    = useRef<SNode[]>([]);
  const rafRef    = useRef<number>(0);
  const iterRef   = useRef(0);
  const dragging  = useRef<string | null>(null);

  // rendered positions (subset of sim state that triggers React re-renders)
  const [pos, setPos]         = useState<{ id: string; x: number; y: number }[]>([]);
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);
  const [highlight, setHL]    = useState<string | null>(null); // community hub-ref
  const [pan, setPan]         = useState({ x: 0, y: 0 });
  const [zoom, setZoom]       = useState(1);
  const panStart              = useRef<{ mx: number; my: number; ox: number; oy: number } | null>(null);

  // ── community membership lookup ────────────────────────────────────────────
  const commOf = useCallback((ref: string): string => {
    for (const [hub, members] of Object.entries(communities)) {
      if (members.includes(ref)) return hub;
    }
    return "__none__";
  }, [communities]);

  // ── (re)init sim ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!nodes.length) return;
    cancelAnimationFrame(rafRef.current);
    simRef.current = buildSim(nodes, edges, width, height);
    iterRef.current = 0;

    function loop() {
      const energy = step(simRef.current, edges, width, height);
      iterRef.current += 1;
      // throttle React state update to ~30fps
      if (iterRef.current % 2 === 0) {
        setPos(simRef.current.map(n => ({ id: n.id, x: n.x, y: n.y })));
      }
      if (energy > STOP_E && iterRef.current < MAX_ITER) {
        rafRef.current = requestAnimationFrame(loop);
      } else {
        setPos(simRef.current.map(n => ({ id: n.id, x: n.x, y: n.y })));
      }
    }
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, width, height]);

  // ── position lookup ────────────────────────────────────────────────────────
  const posOf = useCallback((id: string) => {
    return pos.find(p => p.id === id) ?? { id, x: width / 2, y: height / 2 };
  }, [pos, width, height]);

  // ── node radius ───────────────────────────────────────────────────────────
  const radius = useCallback((id: string) => {
    const s = simRef.current.find(n => n.id === id);
    return 7 + (s?.deg ?? 0) * 2.5;
  }, []);

  // ── drag ──────────────────────────────────────────────────────────────────
  const onNodeMouseDown = (id: string) => (e: React.MouseEvent) => {
    e.stopPropagation();
    dragging.current = id;
  };

  const onSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (panStart.current) {
      const { mx, my, ox, oy } = panStart.current;
      setPan({ x: ox + (e.clientX - mx), y: oy + (e.clientY - my) });
      return;
    }
    if (!dragging.current) return;
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const svgX = (e.clientX - rect.left - pan.x) / zoom;
    const svgY = (e.clientY - rect.top  - pan.y) / zoom;
    const n = simRef.current.find(n => n.id === dragging.current);
    if (n) { n.x = svgX; n.y = svgY; n.vx = 0; n.vy = 0; }
    setPos(simRef.current.map(n => ({ id: n.id, x: n.x, y: n.y })));
  };

  const onSvgMouseUp = () => { dragging.current = null; panStart.current = null; };

  const onBgMouseDown = (e: React.MouseEvent) => {
    panStart.current = { mx: e.clientX, my: e.clientY, ox: pan.x, oy: pan.y };
  };

  // ── zoom ──────────────────────────────────────────────────────────────────
  const onWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.3, Math.min(3, zoom * factor));
    setPan(prev => ({
      x: mx - (mx - prev.x) * (newZoom / zoom),
      y: my - (my - prev.y) * (newZoom / zoom),
    }));
    setZoom(newZoom);
  };

  // ── community membership + dim logic ─────────────────────────────────────
  const isHighlighted = (ref: string) => !highlight || commOf(ref) === highlight;

  // ── short label from ref ──────────────────────────────────────────────────
  const shortLabel = (ref: string) => {
    const section = ref.split("#")[1] ?? ref;
    return section.replace(/-/g, " ");
  };

  // ── community cycle index lookup ─────────────────────────────────────────
  const communityHubs = Object.keys(communities);
  const commColorOf = (ref: string): string => {
    const hub = Object.entries(communities).find(([, members]) => members.includes(ref))?.[0];
    if (!hub) return DEFAULT_COLOR.stroke;
    const idx = communityHubs.indexOf(hub);
    return communityColor(idx);
  };

  // ── legend items (unique sources present) ────────────────────────────────
  const legendSources = [...new Set(nodes.map(n => n.source))];

  if (!nodes.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-line bg-paper">
        <p className="font-mono text-[13px] text-ink-faint">No graph data — click Organize first.</p>
      </div>
    );
  }

  return (
    <div className="relative select-none rounded-xl border border-line bg-paper overflow-hidden">
      {/* Legend */}
      <div className="absolute top-3 left-3 z-10 flex flex-wrap gap-2">
        {legendSources.map(src => {
          const c = palette(src);
          return (
            <button
              key={src}
              onClick={() => setHL(h => h === src ? null : src)}
              className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-mono transition"
              style={{
                borderColor: c.stroke,
                color: c.stroke,
                background: highlight === src ? c.fill : "transparent",
                opacity: highlight && highlight !== src ? 0.4 : 1,
              }}
            >
              <span className="h-2 w-2 rounded-full" style={{ background: c.stroke }} />
              {c.label}
            </button>
          );
        })}
        {highlight && (
          <button
            onClick={() => setHL(null)}
            className="rounded-full border border-line px-2.5 py-1 font-mono text-[11px] text-ink-faint hover:text-ink"
          >
            clear
          </button>
        )}
      </div>

      {/* Hint */}
      <p className="absolute bottom-2 right-3 z-10 font-mono text-[10px] text-ink-faint">
        drag nodes · scroll to zoom · drag canvas to pan
      </p>

      {/* SVG canvas */}
      <svg
        width={width} height={height}
        className="cursor-grab active:cursor-grabbing"
        onMouseMove={onSvgMouseMove}
        onMouseUp={onSvgMouseUp}
        onMouseLeave={onSvgMouseUp}
        onWheel={onWheel}
      >
        <rect
          width={width} height={height} fill="transparent"
          onMouseDown={onBgMouseDown}
        />
        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>

          {/* Edges */}
          {edges.map((e, i) => {
            const s = posOf(e.source), t = posOf(e.target);
            const dim = !isHighlighted(e.source) || !isHighlighted(e.target);
            return (
              <line key={i}
                x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke={
                  e.reason === "dedup_candidate" ? "#b0392b"
                  : e.reason === "shared_terms" ? "#355e7a"
                  : "#d6cbb2"
                }
                strokeWidth={0.8 + e.weight * 3}
                strokeOpacity={dim ? 0.12 : 0.35 + e.weight * 0.5}
                strokeDasharray={e.reason === "dedup_candidate" ? "5 3" : undefined}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map(n => {
            const p = posOf(n.id);
            const c = palette(n.source);
            const r = radius(n.id);
            const dim = !isHighlighted(n.id);
            const label = shortLabel(n.id);
            // When a community is highlighted, use that community's cycle color as the stroke.
            const activeStroke = highlight && !dim ? commColorOf(n.id) : c.stroke;
            return (
              <g key={n.id} transform={`translate(${p.x},${p.y})`}
                 style={{ cursor: "grab" }}
                 onMouseDown={onNodeMouseDown(n.id)}
                 onMouseEnter={e => {
                   const rect = (e.currentTarget.closest("svg") as SVGSVGElement).getBoundingClientRect();
                   setTooltip({ text: n.title, x: e.clientX - rect.left, y: e.clientY - rect.top });
                 }}
                 onMouseLeave={() => setTooltip(null)}
                 onClick={() => setHL(h => h === commOf(n.id) ? null : commOf(n.id))}
              >
                <circle r={r} fill={c.fill} stroke={activeStroke}
                  strokeWidth={dim ? 1 : 2}
                  opacity={dim ? 0.25 : 1}
                />
                {/* degree badge on hub nodes */}
                {(simRef.current.find(s => s.id === n.id)?.deg ?? 0) >= 3 && !dim && (
                  <circle r={4.5} cx={r - 2} cy={-r + 2}
                    fill={c.stroke} opacity={0.85}
                  />
                )}
                <text
                  y={r + 12}
                  textAnchor="middle"
                  fontSize={9}
                  fontFamily="ui-monospace, monospace"
                  fill={c.stroke}
                  opacity={dim ? 0.2 : 0.9}
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {label.length > 22 ? label.slice(0, 20) + "…" : label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-20 max-w-[220px] rounded-lg border border-line bg-paper px-3 py-2 shadow-md"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          <p className="font-mono text-[11px] font-semibold text-ink">{tooltip.text}</p>
        </div>
      )}
    </div>
  );
}
