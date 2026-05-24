"use client";

/**
 * BeforeAfterCTA. The closing pitch.
 *
 * Left pane: simulates the on-call engineer's view at 3am - a fast
 * terminal dump of red/yellow log lines scrolling past, with a slow
 * progress bar inching toward "2:00:00". The chaos.
 *
 * Right pane: simulates IncidentIQ's structured analysis appearing
 * step-by-step, with a fast progress bar hitting 100% in ten seconds.
 * The clarity.
 *
 * The two panes loop together. The contrast IS the product.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Check,
  ChevronRight,
  Clock4,
  TerminalSquare,
} from "lucide-react";

const NOISE_LINES = [
  "2026-05-23T02:58:31Z WARN  checkout-api  pool wait 1.8s",
  "2026-05-23T02:58:35Z INFO  api-gateway   req=GET /healthz 200 4ms",
  "2026-05-23T02:58:41Z DEBUG payments      processing batch=8412",
  "2026-05-23T02:58:47Z WARN  redis-cluster slot moved -> node-3",
  "2026-05-23T02:58:52Z INFO  checkout-api  req=POST /v1/checkout 200 122ms",
  "2026-05-23T02:59:11Z ERROR checkout-api  pool exhausted 200/200",
  "2026-05-23T02:59:14Z ERROR checkout-api  status=503 took 30012ms",
  "2026-05-23T02:59:18Z ERROR payments      Redis CLUSTERDOWN",
  "2026-05-23T02:59:24Z WARN  api-gateway   5xx rate 38% over 1m",
  "2026-05-23T02:59:41Z ERROR notifications worker backlog 14217",
  "2026-05-23T03:00:02Z ERROR checkout-api  CB OPEN payments-worker",
  "2026-05-23T03:00:14Z FATAL payments      OOM heap=512MiB",
  "2026-05-23T03:00:39Z ERROR api-gateway   SLO burn 84x",
  "2026-05-23T03:00:42Z INFO  k8s/payments  CrashLoopBackOff",
  "2026-05-23T03:01:05Z WARN  api-gateway   p99 latency 8.2s",
  "2026-05-23T03:01:17Z ERROR checkout-api  client connection refused",
  "2026-05-23T03:01:33Z INFO  api-gateway   req=GET /healthz 200 4ms",
  "2026-05-23T03:01:45Z DEBUG payments      retry attempt=7 max=10",
];

const ANALYSIS_STEPS: Array<{ label: string; tone: "info" | "warn" | "done" }> = [
  { label: "Reading 1,247 log lines", tone: "info" },
  { label: "Extracting entities: 5 services, 12 errors", tone: "info" },
  { label: "Patient zero located 02:58:31", tone: "warn" },
  { label: "Propagation traced through 4 hops", tone: "info" },
  { label: "Root cause identified", tone: "done" },
  { label: "Top fix ready to copy", tone: "done" },
];

const LOOP_MS = 11_000;

function classifyLine(line: string): "info" | "warn" | "error" | "fatal" | "debug" {
  if (line.includes("FATAL")) return "fatal";
  if (line.includes("ERROR")) return "error";
  if (line.includes("WARN")) return "warn";
  if (line.includes("DEBUG")) return "debug";
  return "info";
}

const LEVEL_CLASS: Record<string, string> = {
  fatal: "text-red-300",
  error: "text-red-300/90",
  warn: "text-amber-300/85",
  info: "text-ink-400",
  debug: "text-ink-500",
};

export function BeforeAfterCTA() {
  // Tick once per second to drive both panes off the same clock.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // Position within the loop, 0..1.
  const t = ((tick * 1000) % LOOP_MS) / LOOP_MS;

  // Left pane: streams a new noise line every ~600ms.
  const visibleNoise = useMemo(() => {
    const count = 7; // window size
    const start = Math.floor((tick * 1.6) % NOISE_LINES.length);
    return Array.from({ length: count }, (_, i) => {
      const idx = (start + i) % NOISE_LINES.length;
      return { id: `${tick}-${i}`, text: NOISE_LINES[idx] };
    });
  }, [tick]);

  // Right pane: reveal analysis steps progressively across the loop.
  const stepsShown = Math.min(
    ANALYSIS_STEPS.length,
    Math.floor(t * (ANALYSIS_STEPS.length + 1)),
  );

  return (
    <section className="mx-auto max-w-6xl px-6 py-24">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-3xl md:text-4xl font-semibold tracking-tight text-ink-50">
          Stop reading logs. Read the answer.
        </h3>
        <p className="mt-3 text-ink-400">
          Stop scrolling logs at 3am. Let the agent tell you what broke, why,
          and exactly how to fix it.
        </p>
      </div>

      <div className="grid md:grid-cols-[1fr,auto,1fr] gap-0 mt-12">
          {/* LEFT: chaos terminal */}
          <Pane
            badge="The old way"
            badgeTone="warn"
            icon={<TerminalSquare className="size-3.5" />}
            label="terminal · 3:02 am"
            progress={Math.min(0.32 + t * 0.04, 0.42)}
            progressLabel="01:47:11 / 02:00:00"
            progressTone="slow"
          >
            <div className="font-mono text-[11.5px] leading-[1.55] h-[176px] overflow-hidden relative">
              <AnimatePresence initial={false}>
                {visibleNoise.map((row, i) => {
                  const level = classifyLine(row.text);
                  return (
                    <motion.div
                      key={row.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1 - i * 0.06, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                      className={"truncate " + LEVEL_CLASS[level]}
                    >
                      {row.text}
                    </motion.div>
                  );
                })}
              </AnimatePresence>
              <div className="pointer-events-none absolute inset-x-0 top-0 h-8 bg-gradient-to-b from-ink-900/70 to-transparent" />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-ink-900/70 to-transparent" />
            </div>
          </Pane>

          {/* Center divider with arrow */}
          <div className="hidden md:flex items-center justify-center px-4">
            <motion.div
              animate={{ x: [0, 4, 0] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
              className="size-9 grid place-items-center rounded-full bg-white/[0.04] border border-white/[0.08]"
            >
              <ChevronRight className="size-4 text-ink-300" />
            </motion.div>
          </div>

          {/* RIGHT: structured analysis */}
          <Pane
            badge="IncidentIQ"
            badgeTone="done"
            icon={<Clock4 className="size-3.5" />}
            label={`agent · ${Math.min(9, Math.floor(t * 9) + 1)}.${Math.floor((t * 9 * 10) % 10)}s`}
            progress={Math.min(1, t * 1.05)}
            progressLabel={`${Math.min(9, Math.floor(t * 9) + 1).toString().padStart(2, "0")} / 10s`}
            progressTone="fast"
          >
            <div className="h-[176px] flex flex-col gap-2 overflow-hidden">
              {ANALYSIS_STEPS.map((step, i) => {
                const active = i < stepsShown;
                const tone =
                  step.tone === "done"
                    ? "text-emerald-300"
                    : step.tone === "warn"
                    ? "text-amber-300"
                    : "text-ink-300";
                return (
                  <motion.div
                    key={i}
                    initial={false}
                    animate={{
                      opacity: active ? 1 : 0.25,
                      x: active ? 0 : -4,
                    }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                    className="flex items-center gap-2.5 text-[13px]"
                  >
                    <span
                      className={
                        "size-4 grid place-items-center rounded-full border " +
                        (active
                          ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                          : "bg-white/[0.03] border-white/[0.08] text-ink-600")
                      }
                    >
                      {active ? <Check className="size-2.5" strokeWidth={3} /> : null}
                    </span>
                    <span className={active ? tone : "text-ink-600"}>
                      {step.label}
                    </span>
                  </motion.div>
                );
              })}
            </div>
          </Pane>
        </div>

      <div className="mt-10 flex justify-center">
        <Link
          href="/dashboard"
          className="btn-primary px-5 py-2.5 text-[14px] group"
        >
          Open the dashboard
          <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
        </Link>
      </div>
    </section>
  );
}

function Pane({
  badge,
  badgeTone,
  icon,
  label,
  progress,
  progressLabel,
  progressTone,
  children,
}: {
  badge: string;
  badgeTone: "warn" | "done";
  icon: React.ReactNode;
  label: string;
  progress: number;
  progressLabel: string;
  progressTone: "slow" | "fast";
  children: React.ReactNode;
}) {
  const badgeClass =
    badgeTone === "warn"
      ? "bg-amber-500/10 text-amber-300 border-amber-500/25"
      : "bg-emerald-500/10 text-emerald-300 border-emerald-500/30";
  const barClass =
    progressTone === "slow"
      ? "bg-gradient-to-r from-amber-500/70 to-amber-400"
      : "bg-gradient-to-r from-emerald-500/70 to-emerald-300";

  return (
    <div className="rounded-2xl border border-white/[0.05] bg-ink-950/50 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.05] bg-ink-950/70">
        <span
          className={
            "chip text-[10px] uppercase tracking-[0.16em] font-semibold border " +
            badgeClass
          }
        >
          {badge}
        </span>
        <div className="ml-auto flex items-center gap-1.5 text-[10.5px] text-ink-500 font-mono">
          {icon}
          <span>{label}</span>
        </div>
      </div>

      <div className="px-4 py-4">{children}</div>

      <div className="px-4 pb-3">
        <div className="flex items-center justify-between text-[10px] font-mono text-ink-500 mb-1 tabular-nums">
          <span>elapsed</span>
          <span>{progressLabel}</span>
        </div>
        <div className="h-1 rounded-full bg-white/[0.05] overflow-hidden">
          <div
            className={"h-full transition-[width] duration-500 ease-out " + barClass}
            style={{ width: `${Math.min(100, progress * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
