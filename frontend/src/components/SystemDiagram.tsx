"use client";

/**
 * SystemDiagram. The visual story of how IncidentIQ actually runs.
 *
 * Left column: telemetry sources (logs, integrations, webhook).
 * Center: the agent (one big pulsing node).
 * Right column: the structured outputs the agent produces.
 *
 * Source nodes connect to the agent with curved SVG paths. The agent
 * connects to each output with another curved path. Small dots travel
 * along the wires on a loop, conveying "data flowing in, analysis
 * flowing out". The agent itself emits a slow pulse ring.
 *
 * This component is intentionally self-contained: a single SVG plus a
 * couple of React-rendered HTML node labels positioned absolutely over
 * the same coordinate space. That way labels stay crisp text while the
 * wires stay vector.
 */

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import {
  Activity,
  Bell,
  Brain,
  Bug,
  FileDown,
  GitBranch,
  Microscope,
  Network,
  TerminalSquare,
  Wrench,
} from "lucide-react";

import { cn } from "@/lib/utils";

type Side = "input" | "agent" | "output";
type LucideIcon = typeof Activity;

interface NodeSpec {
  id: string;
  label: string;
  sub?: string;
  icon: LucideIcon;
  side: Side;
  /** Position in the 1000x600 viewBox. */
  x: number;
  y: number;
}

// ── Coordinate system ────────────────────────────────────────────────────
// The SVG uses a 1000 x 600 viewBox. All node positions and path
// midpoints are expressed in those units so the layout is fully
// resolution-independent.
const VW = 1000;
const VH = 600;

const NODES: NodeSpec[] = [
  // Inputs (left column)
  { id: "logs", label: "Raw logs", sub: "paste · upload", icon: TerminalSquare, side: "input", x: 80, y: 110 },
  { id: "telemetry", label: "Telemetry", sub: "Datadog · Grafana · New Relic", icon: Network, side: "input", x: 80, y: 300 },
  { id: "webhook", label: "Alert webhooks", sub: "PagerDuty · Opsgenie", icon: Bell, side: "input", x: 80, y: 490 },

  // Agent (center)
  { id: "agent", label: "Agent", sub: "Nova Pro", icon: Brain, side: "agent", x: 500, y: 300 },

  // Outputs (right column)
  { id: "rootcause", label: "Root cause", sub: "with quoted evidence", icon: Bug, side: "output", x: 920, y: 80 },
  { id: "forensic", label: "Forensic", sub: "patient zero, blast radius", icon: Microscope, side: "output", x: 920, y: 200 },
  { id: "timeline", label: "Timeline", sub: "chronological cascade", icon: GitBranch, side: "output", x: 920, y: 320 },
  { id: "fixes", label: "Fix recommendations", sub: "ranked, with snippets", icon: Wrench, side: "output", x: 920, y: 440 },
  { id: "pdf", label: "Post mortem PDF", sub: "ready to share", icon: FileDown, side: "output", x: 920, y: 560 },
];

const AGENT = NODES.find((n) => n.id === "agent")!;
const INPUTS = NODES.filter((n) => n.side === "input");
const OUTPUTS = NODES.filter((n) => n.side === "output");

/** Cubic-bezier path between two points with a horizontal pull, like a
 *  flow chart connector. Direction "in" pulls handles outward from each
 *  side; "out" works the other way. */
function curvedPath(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): string {
  const dx = x2 - x1;
  const handle = Math.max(80, Math.abs(dx) * 0.55);
  return `M ${x1} ${y1} C ${x1 + handle} ${y1}, ${x2 - handle} ${y2}, ${x2} ${y2}`;
}

// Pre-compute all wires so SVG and label-positioning code share the
// same source of truth.
interface Wire {
  id: string;
  from: NodeSpec;
  to: NodeSpec;
  d: string;
  /** Pulse animation delay (seconds) so dots don't fire in lockstep. */
  delay: number;
}

const WIRES_IN: Wire[] = INPUTS.map((n, i) => ({
  id: `in-${n.id}`,
  from: n,
  to: AGENT,
  d: curvedPath(n.x + 60, n.y, AGENT.x - 70, AGENT.y),
  delay: i * 0.7,
}));

const WIRES_OUT: Wire[] = OUTPUTS.map((n, i) => ({
  id: `out-${n.id}`,
  from: AGENT,
  to: n,
  d: curvedPath(AGENT.x + 70, AGENT.y, n.x - 60, n.y),
  delay: 1.6 + i * 0.55,
}));

export function SystemDiagram() {
  // Anchor scroll progress to this container. The diagram starts drawing
  // as the top edge enters the bottom of the viewport, and is fully
  // drawn by the time its center hits the center of the viewport.
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 90%", "center 40%"],
  });

  return (
    <div ref={ref} className="relative w-full">
      <svg
        viewBox={`0 0 ${VW} ${VH}`}
        className="w-full h-auto"
        role="presentation"
        aria-hidden
      >
        <defs>
          {/* Soft white-violet gradient used for path strokes. */}
          <linearGradient id="wire" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(167, 139, 250, 0.0)" />
            <stop offset="15%" stopColor="rgba(167, 139, 250, 0.55)" />
            <stop offset="85%" stopColor="rgba(167, 139, 250, 0.55)" />
            <stop offset="100%" stopColor="rgba(167, 139, 250, 0.0)" />
          </linearGradient>
          {/* Halo around the agent node. */}
          <radialGradient id="agentHalo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(167, 139, 250, 0.45)" />
            <stop offset="55%" stopColor="rgba(167, 139, 250, 0.10)" />
            <stop offset="100%" stopColor="rgba(167, 139, 250, 0)" />
          </radialGradient>
        </defs>

        {/* Wires draw themselves driven by scroll progress. Inputs first
            (left-to-center), then outputs (center-to-right). The pulse
            dots only start travelling once each wire has finished
            drawing, so the sequence reads as: data arrives, agent
            thinks, results emit. */}
        {[...WIRES_IN, ...WIRES_OUT].map((w, idx) => (
          <ScrollWire
            key={w.id}
            wire={w}
            index={idx}
            total={WIRES_IN.length + WIRES_OUT.length}
            scrollYProgress={scrollYProgress}
            inputsCount={WIRES_IN.length}
          />
        ))}

        {/* Agent halo (rendered in SVG so it sits inside the same
            coordinate space as the wires) */}
        <circle
          cx={AGENT.x}
          cy={AGENT.y}
          r={120}
          fill="url(#agentHalo)"
        />
      </svg>

      {/* HTML overlay with the actual node chips. Positioned in
          percentages of the SVG viewBox so they stay aligned across
          screen sizes. */}
      <div className="absolute inset-0 pointer-events-none">
        {NODES.map((n) => (
          <DiagramNode key={n.id} node={n} />
        ))}
      </div>
    </div>
  );
}

function ScrollWire({
  wire,
  index,
  total,
  scrollYProgress,
  inputsCount,
}: {
  wire: Wire;
  index: number;
  total: number;
  scrollYProgress: ReturnType<typeof useScroll>["scrollYProgress"];
  inputsCount: number;
}) {
  // Each wire claims a slice of the scroll range. Inputs draw in the
  // first 55% of the scroll arc, outputs in the next 40%. A 5% pad
  // at the end keeps dots visible after the diagram is fully drawn.
  const isInput = index < inputsCount;
  const slot = isInput ? index : index - inputsCount;
  const slotCount = isInput ? inputsCount : total - inputsCount;

  const baseStart = isInput ? 0 : 0.55;
  const baseEnd = isInput ? 0.55 : 0.95;
  const range = baseEnd - baseStart;
  const start = baseStart + (slot / slotCount) * range * 0.6;
  const end = start + range * 0.4;

  const pathLength = useTransform(scrollYProgress, [start, end], [0, 1]);
  // Pulse-dot opacity ramps up after its wire is fully drawn.
  const pulseOpacity = useTransform(scrollYProgress, [end - 0.02, end + 0.05], [0, 1]);

  return (
    <g>
      <motion.path
        d={wire.d}
        stroke="url(#wire)"
        strokeWidth={1.25}
        fill="none"
        strokeLinecap="round"
        style={{ pathLength }}
      />
      <motion.g style={{ opacity: pulseOpacity }}>
        <circle r={3.5} fill="rgb(196, 181, 253)">
          <animateMotion
            dur="2.6s"
            repeatCount="indefinite"
            begin={`${wire.delay}s`}
            path={wire.d}
          />
          <animate
            attributeName="opacity"
            values="0; 1; 1; 0"
            keyTimes="0; 0.1; 0.9; 1"
            dur="2.6s"
            repeatCount="indefinite"
            begin={`${wire.delay}s`}
          />
        </circle>
      </motion.g>
    </g>
  );
}

function DiagramNode({ node }: { node: NodeSpec }) {
  const Icon = node.icon;
  const isAgent = node.side === "agent";

  // Convert viewBox coords to percentage anchors so the node chip
  // positions itself correctly inside the responsive SVG.
  const left = `${(node.x / VW) * 100}%`;
  const top = `${(node.y / VH) * 100}%`;

  return (
    <div
      className={cn(
        "absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto",
        node.side === "input" && "text-left",
        node.side === "output" && "text-left",
        node.side === "agent" && "text-center",
      )}
      style={{ left, top }}
    >
      {isAgent ? (
        <AgentChip node={node} />
      ) : (
        <SatelliteChip node={node} side={node.side} />
      )}
    </div>
  );
}

function AgentChip({ node }: { node: NodeSpec }) {
  const Icon = node.icon;
  return (
    <div className="relative">
      <motion.div
        className="absolute inset-0 rounded-2xl border border-violet-400/30"
        animate={{ scale: [1, 1.25, 1], opacity: [0.6, 0, 0.6] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="relative grid place-items-center size-[120px] rounded-2xl border border-white/[0.10] bg-ink-900/80 backdrop-blur-sm shadow-[0_0_40px_-10px_rgba(167,139,250,0.6)]">
        <Icon className="size-7 text-violet-200" strokeWidth={1.5} />
        <div className="absolute -bottom-9 left-1/2 -translate-x-1/2 whitespace-nowrap text-center">
          <div className="text-[13px] font-semibold text-ink-50">
            {node.label}
          </div>
          <div className="text-[10.5px] uppercase tracking-[0.18em] text-ink-500 mt-0.5 font-mono">
            {node.sub}
          </div>
        </div>
      </div>
    </div>
  );
}

function SatelliteChip({ node, side }: { node: NodeSpec; side: Side }) {
  const Icon = node.icon;
  const alignRight = side === "input";
  return (
    <motion.div
      initial={{ opacity: 0, x: side === "input" ? -8 : 8 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-xl border border-white/[0.07] bg-ink-900/70 backdrop-blur-sm hover:bg-ink-900 hover:border-white/[0.14] transition",
        alignRight ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div className="size-7 grid place-items-center rounded-md bg-white/[0.05] border border-white/[0.07] shrink-0">
        <Icon className="size-3.5 text-ink-200" strokeWidth={1.75} />
      </div>
      <div className={cn("min-w-0", alignRight ? "text-right" : "text-left")}>
        <div className="text-[12.5px] font-medium text-ink-50 leading-tight whitespace-nowrap">
          {node.label}
        </div>
        {node.sub ? (
          <div className="text-[10.5px] text-ink-500 leading-tight mt-0.5 whitespace-nowrap font-mono">
            {node.sub}
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}
