"use client";

import {
  AlertCircle,
  Beaker,
  Bug,
  Clock,
  Crosshair,
  EyeOff,
  GitFork,
  Lightbulb,
  Microscope,
  Skull,
  Sparkles,
  Telescope,
  Timer,
  Workflow,
} from "lucide-react";

import type {
  DeepTraceReport,
  HiddenSignal,
  ServiceProbe,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { FadeItem, StaggerList } from "./motion-primitives";
import { SeverityBadge } from "./SeverityBadge";

const CATEGORY_META: Record<
  string,
  { icon: typeof Bug; label: string; color: string }
> = {
  silent_failure: {
    icon: EyeOff,
    label: "Silent failure",
    color: "text-red-300 border-red-500/30 bg-red-500/[0.05]",
  },
  timing_anomaly: {
    icon: Timer,
    label: "Timing anomaly",
    color: "text-amber-300 border-amber-500/30 bg-amber-500/[0.05]",
  },
  order_anomaly: {
    icon: GitFork,
    label: "Order anomaly",
    color: "text-cyan-300 border-cyan-500/30 bg-cyan-500/[0.05]",
  },
  service_silence: {
    icon: Skull,
    label: "Service silence",
    color: "text-red-300 border-red-500/30 bg-red-500/[0.05]",
  },
  hidden_dependency: {
    icon: Workflow,
    label: "Hidden dependency",
    color: "text-brand-300 border-brand-500/30 bg-brand-500/[0.05]",
  },
};

const ROLE_META: Record<
  string,
  { label: string; chip: string; icon: typeof Bug }
> = {
  primary: {
    label: "PRIMARY",
    chip: "bg-red-500/15 text-red-300 border-red-500/40",
    icon: Crosshair,
  },
  propagator: {
    label: "PROPAGATOR",
    chip: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    icon: Workflow,
  },
  sink: {
    label: "SINK",
    chip: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
    icon: Beaker,
  },
  bystander: {
    label: "BYSTANDER",
    chip: "bg-white/[0.06] text-ink-300 border-white/[0.06]",
    icon: Bug,
  },
};

export function DeepTracePanel({ report }: { report: DeepTraceReport }) {
  return (
    <section className="rounded-2xl border border-amber-500/30 bg-gradient-to-br from-red-500/[0.05] via-ink-900/90 to-amber-500/[0.04] overflow-hidden">
      <header className="px-5 py-4 border-b border-white/[0.06] flex items-center gap-3 flex-wrap">
        <div className="size-10 grid place-items-center rounded-xl bg-amber-500/15 border border-amber-500/40 text-amber-300">
          <Telescope className="size-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] uppercase tracking-[0.22em] text-amber-300 font-bold">
              Deep Trace · Emergency Investigator
            </span>
            {report.auto_triggered ? (
              <span className="chip bg-red-500/15 text-red-300 border-red-500/30">
                Auto-escalated
              </span>
            ) : (
              <span className="chip">Manually invoked</span>
            )}
          </div>
          <h3 className="mt-1 text-base font-semibold text-ink-50 leading-snug">
            {report.triggered_reason}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {report.extended_model_used ? (
            <span className="chip bg-brand-500/10 text-brand-200 border-brand-500/30">
              <Sparkles className="size-3" /> {report.extended_model_used}
            </span>
          ) : null}
          <span className="chip">
            <Clock className="size-3" /> {(report.duration_ms / 1000).toFixed(1)}s
          </span>
        </div>
      </header>

      <StaggerList variant="stagger" className="p-5 space-y-5">
        {report.revised_confidence > 0 || report.revised_root_cause ? (
          <FadeItem>
            <RevisedVerdict report={report} />
          </FadeItem>
        ) : null}

        <FadeItem>
          {report.hidden_signals.length > 0 ? (
            <HiddenBugs signals={report.hidden_signals} />
          ) : (
            <EmptyScanState />
          )}
        </FadeItem>

        {report.service_probes.length > 0 ? (
          <FadeItem>
            <ServiceProbes probes={report.service_probes} />
          </FadeItem>
        ) : null}

        {report.expert_insights.length > 0 ? (
          <FadeItem>
            <ExpertInsights insights={report.expert_insights} />
          </FadeItem>
        ) : null}
      </StaggerList>
    </section>
  );
}

function RevisedVerdict({ report }: { report: DeepTraceReport }) {
  const pct = Math.round(report.revised_confidence * 100);
  return (
    <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.05] p-4">
      <div className="flex items-start gap-3">
        <div className="size-8 grid place-items-center rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 shrink-0">
          <Microscope className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10.5px] uppercase tracking-[0.18em] text-emerald-300 font-bold">
              Verdict after deep investigation
            </span>
            {pct > 0 ? (
              <span className="text-[11px] text-ink-400 font-mono">
                confidence: {pct}%
              </span>
            ) : null}
          </div>
          {report.revised_root_cause ? (
            <p className="mt-1.5 text-[14px] text-ink-100 leading-relaxed">
              {report.revised_root_cause}
            </p>
          ) : (
            <p className="mt-1.5 text-[13px] text-ink-300">
              Deep Trace verified the original root cause — confidence promoted from
              the regular pass.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function HiddenBugs({ signals }: { signals: HiddenSignal[] }) {
  return (
    <div>
      <SectionHeader
        icon={<Bug className="size-3.5 text-red-300" />}
        label="Hidden bugs the surface pass missed"
        count={signals.length}
      />
      <div className="space-y-2.5">
        {signals.map((signal, i) => (
          <HiddenBugCard key={`${signal.category}-${i}`} signal={signal} />
        ))}
      </div>
    </div>
  );
}

function HiddenBugCard({ signal }: { signal: HiddenSignal }) {
  const meta = CATEGORY_META[signal.category] ?? CATEGORY_META.hidden_dependency;
  const Icon = meta.icon;
  return (
    <div className={cn("rounded-xl border p-4", meta.color)}>
      <div className="flex items-start gap-3">
        <div className="size-8 grid place-items-center rounded-lg bg-white/[0.06] border border-white/[0.08] shrink-0">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10.5px] uppercase tracking-[0.18em] font-bold">
              {meta.label}
            </span>
            {signal.severity ? <SeverityBadge severity={signal.severity} /> : null}
            <span className="text-[13px] font-semibold text-ink-50">
              {signal.title}
            </span>
          </div>
          <p className="mt-1 text-[13px] text-ink-300 leading-snug">
            {signal.detail}
          </p>
          {signal.evidence.length > 0 ? (
            <div className="mt-2 space-y-1">
              {signal.evidence.map((line, i) => (
                <code
                  key={i}
                  className="block font-mono text-[11.5px] text-ink-300 leading-snug bg-ink-950/60 border border-white/[0.05] rounded px-2.5 py-1.5 break-all whitespace-pre-wrap"
                >
                  {line}
                </code>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ServiceProbes({ probes }: { probes: ServiceProbe[] }) {
  return (
    <div>
      <SectionHeader
        icon={<Microscope className="size-3.5 text-brand-300" />}
        label="Per-service deep probe"
        count={probes.length}
      />
      <StaggerList variant="stagger" className="grid sm:grid-cols-2 gap-2.5">
        {probes.map((probe) => (
          <FadeItem key={probe.service}>
            <ServiceProbeCard probe={probe} />
          </FadeItem>
        ))}
      </StaggerList>
    </div>
  );
}

function ServiceProbeCard({ probe }: { probe: ServiceProbe }) {
  const meta = ROLE_META[probe.suspected_role_in_cascade] ?? ROLE_META.bystander;
  const RoleIcon = meta.icon;
  return (
    <div
      className={cn(
        "rounded-xl border border-white/[0.06] bg-ink-950/40 p-3.5 hover:bg-ink-950/60 transition",
        probe.suspected_role_in_cascade === "primary" &&
          "border-red-500/30 bg-red-500/[0.04]",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="size-8 grid place-items-center rounded-lg bg-white/[0.06] border border-white/[0.06] shrink-0">
          <RoleIcon className="size-4 text-ink-300" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13.5px] font-medium text-ink-50 truncate">
              {probe.service}
            </span>
            <span className={cn("chip", meta.chip)}>{meta.label}</span>
          </div>
          <div className="text-[10.5px] uppercase tracking-wider text-ink-500 mt-0.5">
            {probe.role}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-2 text-[11px] text-ink-400 font-mono">
            <span>lines: {probe.line_count}</span>
            <span>·</span>
            <span>burst: {probe.error_burst_rate}/m</span>
            {probe.went_silent ? (
              <>
                <span>·</span>
                <span className="text-red-300">went silent</span>
              </>
            ) : null}
          </div>
          {probe.findings.length > 0 ? (
            <ul className="mt-2 space-y-1 text-[12.5px] text-ink-300">
              {probe.findings.map((finding, i) => (
                <li key={i} className="flex items-start gap-1.5 leading-snug">
                  <span className="text-ink-500 mt-0.5">•</span>
                  <span>{finding}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ExpertInsights({ insights }: { insights: string[] }) {
  return (
    <div>
      <SectionHeader
        icon={<Lightbulb className="size-3.5 text-amber-300" />}
        label="Expert insights from extended LLM pass"
        count={insights.length}
      />
      <div className="space-y-2">
        {insights.map((insight, i) => (
          <div
            key={i}
            className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-3"
          >
            <span className="size-6 grid place-items-center rounded-md bg-amber-500/20 border border-amber-500/30 text-amber-300 font-mono text-[11px] font-semibold shrink-0">
              {i + 1}
            </span>
            <p className="text-[13px] text-ink-200 leading-relaxed">{insight}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function SectionHeader({
  icon,
  label,
  count,
}: {
  icon: React.ReactNode;
  label: string;
  count: number;
}) {
  return (
    <div className="flex items-center gap-2 mb-3">
      {icon}
      <span className="text-[10.5px] uppercase tracking-[0.18em] text-ink-400 font-bold">
        {label}
      </span>
      <span className="text-[10.5px] text-ink-500">({count})</span>
    </div>
  );
}

function EmptyScanState() {
  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-3 text-[13px] text-ink-300 flex items-start gap-2">
      <AlertCircle className="size-4 text-emerald-300 mt-0.5 shrink-0" />
      <span>
        All four hidden-signal scanners came back clean. Deep Trace found no
        subtle defects beyond what the regular pass already identified.
      </span>
    </div>
  );
}
