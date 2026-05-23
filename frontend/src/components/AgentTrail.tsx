"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  ChevronDown,
  ChevronRight,
  Eye,
  Flag,
  Wrench,
} from "lucide-react";

import type { AgentStep } from "@/lib/types";
import { cn } from "@/lib/utils";
import { transitions } from "@/lib/motion";

const KIND_META: Record<
  string,
  { icon: typeof Brain; chip: string; ring: string; label: string }
> = {
  thought: {
    icon: Brain,
    chip: "bg-brand-500/15 text-brand-300 border-brand-500/30",
    ring: "ring-brand-500/30",
    label: "thought",
  },
  tool_call: {
    icon: Wrench,
    chip: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    ring: "ring-amber-500/30",
    label: "tool call",
  },
  observation: {
    icon: Eye,
    chip: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
    ring: "ring-cyan-500/30",
    label: "observation",
  },
  decision: {
    icon: Flag,
    chip: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    ring: "ring-emerald-500/30",
    label: "decision",
  },
};

export function AgentTrail({ steps }: { steps: AgentStep[] }) {
  if (steps.length === 0) {
    return (
      <div className="text-sm text-ink-500 italic">
        No agent trace recorded for this analysis.
      </div>
    );
  }

  return (
    <ol className="relative space-y-2">
      <span className="absolute left-3.5 top-3 bottom-3 w-px bg-gradient-to-b from-white/[0.06] via-white/[0.10] to-white/[0.06]" />
      {steps.map((step) => (
        <StepRow key={step.step} step={step} />
      ))}
    </ol>
  );
}

function StepRow({ step }: { step: AgentStep }) {
  const meta = KIND_META[step.kind] ?? KIND_META.thought;
  const Icon = meta.icon;
  const [open, setOpen] = useState(false);
  const hasOutput =
    step.output !== undefined && step.output !== null && step.kind === "observation";

  return (
    <motion.li
      initial={{ opacity: 0, y: 6, x: -4 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      transition={transitions.base}
      className="relative grid grid-cols-[2rem,1fr] gap-3"
    >
      <span
        className={cn(
          "relative z-10 size-7 grid place-items-center rounded-full bg-ink-950 ring-4 ring-ink-950",
        )}
      >
        <span
          className={cn(
            "size-7 grid place-items-center rounded-full border bg-ink-900 ring-1",
            meta.chip,
            meta.ring,
          )}
        >
          <Icon className="size-3.5" />
        </span>
      </span>
      <div className="min-w-0 pb-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10.5px] font-mono text-ink-500 tabular-nums">
            #{step.step.toString().padStart(2, "0")}
          </span>
          <span className={cn("chip", meta.chip)}>{meta.label}</span>
          <span className="text-sm font-medium text-ink-50 truncate">
            {step.title}
          </span>
          {step.tool ? (
            <span className="chip text-[10.5px]">{step.tool}()</span>
          ) : null}
        </div>
        <p className="mt-1 text-[12.5px] text-ink-300 leading-snug">
          {step.detail}
        </p>
        {hasOutput ? (
          <button
            onClick={() => setOpen((o) => !o)}
            className="mt-1.5 text-[11.5px] text-brand-300 hover:text-brand-200 inline-flex items-center gap-1"
          >
            {open ? (
              <ChevronDown className="size-3" />
            ) : (
              <ChevronRight className="size-3" />
            )}
            {open ? "Hide" : "Inspect"} tool output
          </button>
        ) : null}
        {open && hasOutput ? (
          <motion.pre
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            transition={transitions.base}
            className="mt-2 max-h-72 overflow-auto rounded-lg bg-ink-950/80 border border-white/[0.06] p-3 text-[11.5px] font-mono text-ink-300 leading-relaxed"
          >
            {JSON.stringify(step.output, null, 2)}
          </motion.pre>
        ) : null}
      </div>
    </motion.li>
  );
}
