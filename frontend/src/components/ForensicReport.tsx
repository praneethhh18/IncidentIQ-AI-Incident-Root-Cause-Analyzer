import {
  AlertTriangle,
  ArrowRight,
  Crosshair,
  Database,
  GitBranch,
  Globe,
  Layers,
  Microscope,
  Network,
  Radar,
  Server,
  Users,
  Workflow,
  Zap,
} from "lucide-react";

import type {
  BlastRadiusEntity,
  ForensicReport as ForensicReportType,
} from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";
import { SeverityBadge } from "./SeverityBadge";

const KIND_ICON: Record<string, typeof Server> = {
  service: Server,
  dependency: Database,
  user_segment: Users,
  region: Globe,
  data: Layers,
};

export function ForensicReport({ forensic }: { forensic: ForensicReportType }) {
  return (
    <section className="rounded-2xl border border-brand-500/20 bg-gradient-to-br from-brand-500/[0.06] via-ink-900/80 to-ink-950 overflow-hidden">
      <header className="flex items-center gap-3 px-5 py-4 border-b border-white/[0.06]">
        <div className="size-9 grid place-items-center rounded-xl bg-brand-500/15 border border-brand-500/30 text-brand-300">
          <Microscope className="size-4" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold tracking-wide text-ink-50 uppercase">
            Forensic report
          </h3>
          <p className="text-[12px] text-ink-400 mt-0.5">
            Reverse-engineered view: where the cascade started, how it spread,
            what it touched, what likely triggered it.
          </p>
        </div>
        {forensic.minutes_to_detection !== null ? (
          <div className="chip bg-amber-500/10 text-amber-300 border-amber-500/30">
            <Zap className="size-3" /> MTTD: {forensic.minutes_to_detection}m
          </div>
        ) : null}
      </header>

      <div className="p-5 space-y-5">
        <PatientZero forensic={forensic} />
        <PropagationPath path={forensic.propagation_path} />
        <BlastRadius entities={forensic.blast_radius} />
        <TriggerHypothesis forensic={forensic} />
      </div>
    </section>
  );
}

function PatientZero({ forensic }: { forensic: ForensicReportType }) {
  const pz = forensic.patient_zero;
  return (
    <div className="rounded-xl border border-red-500/25 bg-red-500/[0.04] p-4">
      <div className="flex items-start gap-3">
        <div className="size-9 grid place-items-center rounded-lg bg-red-500/15 border border-red-500/30 text-red-300 shrink-0">
          <Crosshair className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10.5px] uppercase tracking-[0.18em] text-red-300 font-semibold">
              Patient zero
            </span>
            <span className="font-mono text-[11px] text-ink-500 tabular-nums">
              {formatTime(pz.timestamp)}
            </span>
            <SeverityBadge severity={pz.severity} />
          </div>
          <div className="mt-1.5 text-[14px] font-medium text-ink-50">
            {pz.label}
          </div>
          <p className="mt-1 text-[13px] text-ink-300 leading-snug">
            {pz.detail}
          </p>
        </div>
      </div>
    </div>
  );
}

function PropagationPath({ path }: { path: string[] }) {
  if (path.length === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-2 mb-2.5">
        <GitBranch className="size-3.5 text-brand-300" />
        <span className="text-[10.5px] uppercase tracking-[0.18em] text-ink-400 font-semibold">
          Propagation path
        </span>
        <span className="text-[10.5px] text-ink-500">
          ({path.length} hops)
        </span>
      </div>
      <div className="flex items-center gap-1 flex-wrap p-3 rounded-xl bg-ink-950/60 border border-white/[0.05]">
        {path.map((node, i) => (
          <PathNode key={`${node}-${i}`} node={node} index={i} last={i === path.length - 1} />
        ))}
      </div>
    </div>
  );
}

function PathNode({
  node,
  index,
  last,
}: {
  node: string;
  index: number;
  last: boolean;
}) {
  const intensity = Math.min(1, 0.35 + index * 0.12);
  return (
    <>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[12px] font-mono text-ink-100 border transition",
          "bg-ink-900/80 border-white/[0.08]",
        )}
        style={{
          boxShadow: `inset 0 0 0 1px rgba(99, 102, 241, ${intensity * 0.3})`,
          background: `rgba(99, 102, 241, ${intensity * 0.08})`,
        }}
      >
        {index === 0 ? (
          <Crosshair className="size-3 text-red-300" />
        ) : (
          <span className="size-1.5 rounded-full bg-brand-400" />
        )}
        {node}
      </span>
      {!last ? (
        <ArrowRight className="size-3.5 text-ink-500 mx-0.5 shrink-0" />
      ) : null}
    </>
  );
}

function BlastRadius({ entities }: { entities: BlastRadiusEntity[] }) {
  if (entities.length === 0) return null;
  // Group entities by kind for visual structure.
  const groups: Record<string, BlastRadiusEntity[]> = {};
  for (const entity of entities) {
    (groups[entity.kind] ??= []).push(entity);
  }
  const order = ["user_segment", "service", "dependency", "data", "region"];
  const sortedKinds = Object.keys(groups).sort(
    (a, b) =>
      (order.indexOf(a) === -1 ? 99 : order.indexOf(a)) -
      (order.indexOf(b) === -1 ? 99 : order.indexOf(b)),
  );

  return (
    <div>
      <div className="flex items-center gap-2 mb-2.5">
        <Radar className="size-3.5 text-brand-300" />
        <span className="text-[10.5px] uppercase tracking-[0.18em] text-ink-400 font-semibold">
          Blast radius
        </span>
        <span className="text-[10.5px] text-ink-500">
          ({entities.length} entities touched)
        </span>
      </div>
      <div className="space-y-3">
        {sortedKinds.map((kind) => (
          <BlastGroup key={kind} kind={kind} entities={groups[kind]} />
        ))}
      </div>
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  service: "Services",
  dependency: "Dependencies",
  user_segment: "User impact",
  region: "Regions",
  data: "Data surfaces",
};

function BlastGroup({
  kind,
  entities,
}: {
  kind: string;
  entities: BlastRadiusEntity[];
}) {
  const Icon = KIND_ICON[kind] ?? Network;
  return (
    <div className="rounded-xl border border-white/[0.05] bg-ink-950/40 p-3">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="size-3.5 text-ink-400" />
        <span className="text-[11px] uppercase tracking-wider text-ink-400 font-semibold">
          {KIND_LABEL[kind] ?? kind}
        </span>
        <span className="text-[10.5px] text-ink-500">({entities.length})</span>
      </div>
      <div className="grid sm:grid-cols-2 gap-2">
        {entities.map((entity, i) => (
          <div
            key={`${entity.name}-${i}`}
            className="rounded-lg bg-white/[0.02] border border-white/[0.05] px-3 py-2 hover:bg-white/[0.04] transition"
          >
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-medium text-ink-50 truncate">
                {entity.name}
              </span>
              {entity.severity ? (
                <SeverityBadge severity={entity.severity} className="ml-auto text-[10px] px-1.5 py-0.5" />
              ) : null}
            </div>
            <div className="text-[12px] text-ink-400 mt-0.5 leading-snug">
              {entity.impact}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TriggerHypothesis({ forensic }: { forensic: ForensicReportType }) {
  const pct = Math.round(forensic.trigger_confidence * 100);
  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-4">
      <div className="flex items-start gap-3">
        <div className="size-9 grid place-items-center rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-300 shrink-0">
          <AlertTriangle className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10.5px] uppercase tracking-[0.18em] text-amber-300 font-semibold">
              Trigger hypothesis
            </span>
            <span className="text-[10.5px] text-ink-500 font-mono tabular-nums">
              {pct}% confidence
            </span>
          </div>
          <p className="mt-1.5 text-[13.5px] text-ink-100 leading-relaxed">
            {forensic.trigger_hypothesis}
          </p>
          <div className="mt-2 h-1 rounded-full bg-white/[0.05] overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-amber-500 via-amber-400 to-emerald-400"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
