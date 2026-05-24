"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

import { EASE } from "@/lib/motion";
import { FadeIn } from "@/components/motion-primitives";
import { BeforeAfterCTA } from "@/components/BeforeAfterCTA";
import { ScrollRevealText } from "@/components/ScrollRevealText";
import { SystemDiagram } from "@/components/SystemDiagram";

import { cn } from "@/lib/utils";

export default function Landing() {
  return (
    <>
      <Hero />
      <SocialProof />
      <Features />
      <HowItWorks />
      <BeforeAfterCTA />
    </>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 bg-dots opacity-30 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" />

      <div className="relative mx-auto max-w-7xl px-6 pt-20 pb-24 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE, delay: 0.08 }}
          className="text-5xl md:text-6xl font-semibold tracking-tight text-ink-50 leading-[1.05]"
        >
          Find the root cause
          <br />
          before the page bounces.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE, delay: 0.18 }}
          className="mt-6 max-w-2xl mx-auto text-ink-400 text-lg leading-relaxed"
        >
          IncidentIQ reads your logs, traces the cascade back to patient zero, and writes the post mortem while you're still reading the alert.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE, delay: 0.28 }}
          className="mt-10 flex items-center justify-center gap-2"
        >
          <Link href="/dashboard" className="btn-primary px-5 py-2.5 text-[14px] group">
            Analyze an incident
            <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
          </Link>
          <Link href="/incidents" className="btn-secondary px-5 py-2.5 text-[14px]">
            View history
          </Link>
        </motion.div>

        <FadeIn delay={0.4}>
          <div className="mt-8 text-[12px] text-ink-500">
            Three realistic incidents preloaded. No keys needed to try it.
          </div>
        </FadeIn>
      </div>

      <HeroPreview />
    </section>
  );
}

// ── Demo scenarios ───────────────────────────────────────────────────────
// Three real incident shapes drawn from the backend's demo_data.py. The
// hero panel cycles through them on a loop, so the page feels like a
// running product demo rather than a static screenshot.

type Sev = "p1" | "p2" | "p3";

interface Scenario {
  id: string;
  severity: "P1" | "P2" | "P3";
  title: string;
  rootCause: string;
  summary: React.ReactNode;
  stats: { confidence: number; services: number; blast: number };
  cascade: { t: string; l: string; s: Sev }[];
}

const SCENARIOS: Scenario[] = [
  {
    id: "INC-A4F12C9B",
    severity: "P1",
    title: "Cascading checkout failure",
    rootCause: "Postgres writer pool exhausted on checkout-api.",
    summary: (
      <>
        A long-running query held connections past pool timeout, back-pressuring{" "}
        <span className="text-ink-200 font-medium">payments-worker</span> until
        Redis hit CLUSTERDOWN. The api-gateway tripped its circuit breaker.
        SLO burn 84x.
      </>
    ),
    stats: { confidence: 92, services: 5, blast: 7 },
    cascade: [
      { t: "02:58:12", l: "DB pool pressure begins", s: "p3" },
      { t: "02:59:11", l: "Pool exhausted", s: "p2" },
      { t: "02:59:18", l: "Redis CLUSTERDOWN", s: "p1" },
      { t: "03:00:02", l: "Circuit breaker opens", s: "p1" },
      { t: "03:00:14", l: "payments-worker OOM", s: "p1" },
    ],
  },
  {
    id: "INC-B7D219E4",
    severity: "P2",
    title: "Recommendations memory leak",
    rootCause: "UserSimilarityCache growing unbounded in the JVM heap.",
    summary: (
      <>
        An in-process cache without max-size or TTL filled the JVM heap. Pod
        OOMKilled every ~50 minutes.{" "}
        <span className="text-ink-200 font-medium">18%</span> of users seeing
        fallback recommendations.
      </>
    ),
    stats: { confidence: 88, services: 2, blast: 4 },
    cascade: [
      { t: "15:30:22", l: "Heap usage 60%", s: "p3" },
      { t: "16:48:11", l: "Heap usage 79%", s: "p2" },
      { t: "17:22:08", l: "Full GC pause 1.2s", s: "p2" },
      { t: "17:51:30", l: "java.lang.OutOfMemoryError", s: "p1" },
      { t: "17:51:31", l: "Pod OOMKilled, restart 5/4h", s: "p1" },
    ],
  },
  {
    id: "INC-91F3D5A8",
    severity: "P1",
    title: "RDS failover, replica lag",
    rootCause: "Aurora writer failover with 18s replica lag, stale reads.",
    summary: (
      <>
        Sustained slow queries triggered an Aurora failover. New replicas were{" "}
        <span className="text-ink-200 font-medium">18.4s behind</span> the
        writer, causing read-after-write inconsistencies on captured payments.
      </>
    ),
    stats: { confidence: 84, services: 3, blast: 5 },
    cascade: [
      { t: "08:42:11", l: "SlowQuery 4.2s on orders", s: "p3" },
      { t: "08:43:18", l: "Writer connection lost", s: "p2" },
      { t: "08:43:18", l: "Failover to standby", s: "p2" },
      { t: "08:44:01", l: "Replica lag 18.4s", s: "p1" },
      { t: "08:44:09", l: "Stale read on order #91823", s: "p1" },
    ],
  },
];

// One scenario = N cascade ticks at TICK_MS each + HOLD ticks at the end.
const TICK_MS = 900;
const HOLD_TICKS = 2;

function HeroPreview() {
  // Global tick. Drives both which scenario is showing and how many
  // cascade events have surfaced within it.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), TICK_MS);
    return () => clearInterval(id);
  }, []);

  // Scenarios all have 5 cascade rows. Each scenario "owns"
  // (rows + HOLD_TICKS) ticks. After that we advance.
  const ticksPerScenario = SCENARIOS[0].cascade.length + HOLD_TICKS;
  const scenarioIdx = Math.floor(tick / ticksPerScenario) % SCENARIOS.length;
  const localTick = tick % ticksPerScenario;
  const scenario = SCENARIOS[scenarioIdx];
  const surfaced = Math.min(localTick, scenario.cascade.length);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.7, ease: EASE, delay: 0.35 }}
      className="relative mx-auto max-w-6xl px-6 pb-20"
    >
      <div className="relative rounded-2xl border border-white/[0.07] bg-ink-900/60 backdrop-blur overflow-hidden shadow-glow">
        {/* Persistent header bar (animates only the changing parts) */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-white/[0.05] bg-ink-900/80">
          <AnimatePresence mode="popLayout">
            <motion.span
              key={`sev-${scenario.id}`}
              initial={{ opacity: 0, y: -3 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 3 }}
              transition={{ duration: 0.3, ease: EASE }}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10.5px] font-semibold border",
                scenario.severity === "P1" &&
                  "text-sev-p1 bg-sev-p1/10 border-sev-p1/25",
                scenario.severity === "P2" &&
                  "text-sev-p2 bg-sev-p2/10 border-sev-p2/25",
                scenario.severity === "P3" &&
                  "text-sev-p3 bg-sev-p3/10 border-sev-p3/25",
              )}
            >
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  scenario.severity === "P1" && "bg-sev-p1",
                  scenario.severity === "P2" && "bg-sev-p2",
                  scenario.severity === "P3" && "bg-sev-p3",
                )}
              />
              {scenario.severity}
            </motion.span>
          </AnimatePresence>

          <AnimatePresence mode="popLayout">
            <motion.span
              key={`id-${scenario.id}`}
              initial={{ opacity: 0, y: -3 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 3 }}
              transition={{ duration: 0.3, ease: EASE, delay: 0.05 }}
              className="font-mono text-[11px] text-ink-400 tabular-nums"
            >
              {scenario.id}
            </motion.span>
          </AnimatePresence>

          <span className="text-ink-700">·</span>

          <AnimatePresence mode="popLayout">
            <motion.span
              key={`title-${scenario.id}`}
              initial={{ opacity: 0, y: -3 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 3 }}
              transition={{ duration: 0.3, ease: EASE, delay: 0.1 }}
              className="text-[11.5px] text-ink-400 truncate"
            >
              {scenario.title}
            </motion.span>
          </AnimatePresence>

          <span className="ml-auto flex items-center gap-3">
            <ScenarioDots active={scenarioIdx} count={SCENARIOS.length} />
            <span className="flex items-center gap-1.5">
              <span className="relative inline-flex size-1.5">
                <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-70" />
                <span className="relative size-1.5 rounded-full bg-emerald-400" />
              </span>
              <span className="font-mono text-[10.5px] text-ink-400 tabular-nums tracking-wider">
                LIVE DEMO
              </span>
            </span>
          </span>
        </div>

        {/* Body: crossfades on scenario change. min-height locks the
            visual size so cascades of differing label lengths don't jitter. */}
        <div className="relative min-h-[300px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={scenario.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.4, ease: EASE }}
              className="grid md:grid-cols-[1.5fr,1fr] gap-0"
            >
              <div className="p-7 border-b md:border-b-0 md:border-r border-white/[0.05]">
                <div className="text-[10.5px] uppercase tracking-[0.18em] text-ink-500 font-semibold">
                  Root cause
                </div>
                <h3 className="mt-2 text-[22px] font-semibold tracking-tight text-ink-50 leading-snug">
                  {scenario.rootCause}
                </h3>
                <p className="mt-3 text-[13.5px] text-ink-400 leading-relaxed">
                  {scenario.summary}
                </p>

                <div className="mt-6 grid grid-cols-3 gap-x-6 gap-y-1">
                  <Stat label="Confidence">
                    <CountTo to={scenario.stats.confidence} suffix="%" />
                  </Stat>
                  <Stat label="Services">
                    <CountTo to={scenario.stats.services} />
                  </Stat>
                  <Stat label="Blast radius">
                    <CountTo to={scenario.stats.blast} />
                  </Stat>
                </div>
              </div>

              <CascadePane
                events={scenario.cascade}
                surfaced={surfaced}
              />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

function ScenarioDots({ active, count }: { active: number; count: number }) {
  return (
    <span className="flex items-center gap-1">
      {Array.from({ length: count }, (_, i) => (
        <span
          key={i}
          className={cn(
            "h-[3px] rounded-full transition-all duration-500",
            i === active
              ? "w-5 bg-ink-100"
              : "w-2 bg-ink-700",
          )}
        />
      ))}
    </span>
  );
}

function CascadePane({
  events,
  surfaced,
}: {
  events: { t: string; l: string; s: Sev }[];
  surfaced: number;
}) {
  return (
    <div className="p-7 bg-ink-950/30">
      <div className="flex items-center justify-between mb-4">
        <div className="text-[10.5px] uppercase tracking-[0.18em] text-ink-500 font-semibold">
          Cascade
        </div>
        <div className="font-mono text-[10.5px] text-ink-500 tabular-nums">
          step {Math.min(surfaced, events.length)}/{events.length}
        </div>
      </div>
      <ol className="relative space-y-3">
        <span className="absolute left-[3.95rem] top-1 bottom-1 w-px bg-white/[0.06]" />
        {events.map((event, i) => {
          const state =
            i < surfaced ? "past" : i === surfaced ? "active" : "future";
          return (
            <li
              key={`${event.t}-${i}`}
              className="relative grid grid-cols-[3.6rem,1rem,1fr] items-center gap-2 text-[12.5px]"
            >
              <span
                className={cn(
                  "font-mono text-[10.5px] tabular-nums text-right transition-colors duration-300",
                  state === "future" ? "text-ink-700" : "text-ink-500",
                )}
              >
                {event.t}
              </span>
              <span className="grid place-items-center">
                <motion.span
                  animate={
                    state === "active" ? { scale: [1, 1.4, 1] } : { scale: 1 }
                  }
                  transition={{
                    duration: 0.8,
                    repeat: state === "active" ? Infinity : 0,
                    ease: "easeInOut",
                  }}
                  className={cn(
                    "sev-dot ring-4 ring-ink-950 transition-all duration-300",
                    `sev-dot-${event.s}`,
                    state === "future" && "opacity-25 !shadow-none",
                    state === "past" && "opacity-90",
                    state === "active" && "opacity-100",
                  )}
                />
              </span>
              <span
                className={cn(
                  "truncate transition-colors duration-300",
                  state === "future"
                    ? "text-ink-700"
                    : state === "active"
                    ? "text-ink-50 font-medium"
                    : "text-ink-300",
                )}
              >
                {event.l}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Lightweight count-up that animates whenever its `to` changes (so a
 *  scenario switch counts fresh). Doesn't depend on `useInView` because
 *  the parent crossfade already gates visibility. */
function CountTo({ to, suffix = "" }: { to: number; suffix?: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const start = performance.now();
    const duration = 900;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(2, -10 * t);
      setN(Math.round(to * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
      else setN(to);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return (
    <span className="tabular-nums">
      {n}
      {suffix}
    </span>
  );
}

function Stat({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.16em] text-ink-500 font-semibold">
        {label}
      </div>
      <div className="text-[22px] font-semibold tracking-tight text-ink-50 tabular-nums mt-1">
        {children}
      </div>
    </div>
  );
}

function SocialProof() {
  // simpleicons.org CDN serves single-color SVG brand marks. We use a
  // grey hex (Tailwind's slate-400 ~ 9ca3af) so the row stays muted on
  // the landing page; opacity bumps on hover. CC0 licensed, no API key.
  const integrations: { slug: string; name: string }[] = [
    { slug: "datadog", name: "Datadog" },
    { slug: "grafana", name: "Grafana" },
    { slug: "newrelic", name: "New Relic" },
    { slug: "pagerduty", name: "PagerDuty" },
    { slug: "atlassian", name: "Opsgenie" },
    { slug: "slack", name: "Slack" },
    { slug: "github", name: "GitHub" },
  ];
  return (
    <section className="border-y border-white/[0.05] bg-ink-950/50">
      <div className="mx-auto max-w-7xl px-6 py-8 flex flex-wrap items-center justify-center gap-x-10 sm:gap-x-12 gap-y-5 text-ink-500">
        <span className="text-[11px] uppercase tracking-[0.2em]">
          Integrates with
        </span>
        {integrations.map((i) => (
          <span
            key={i.slug}
            title={i.name}
            className="inline-flex items-center"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`https://cdn.simpleicons.org/${i.slug}/9ca3af`}
              alt={i.name}
              className="h-5 sm:h-6 opacity-70 hover:opacity-100 transition"
            />
          </span>
        ))}
      </div>
    </section>
  );
}

function Features() {
  return (
    <section className="mx-auto max-w-7xl px-6 py-24">
      <div className="max-w-2xl">
        <div className="chip">How it&apos;s wired</div>
        <h2 className="mt-4 text-3xl md:text-4xl font-semibold tracking-tight text-ink-50">
          Built like a senior SRE thinks.
        </h2>
        <p className="mt-3 text-ink-400 leading-relaxed">
          Telemetry flows in from your existing stack. One agent reads it,
          investigates it with eight tools, and emits a structured analysis
          ready to act on. No copilots to chat with. No prompts to write.
        </p>
      </div>

      <div className="mt-14">
        <SystemDiagram />
      </div>
    </section>
  );
}


// Three step cards. Each has an accent palette that gets used for its
// number badge, ambient inner glow, and border tint. The colors progress
// neutral -> violet -> emerald to suggest "raw input -> active analysis
// -> finished result".
const STEP_PANELS = [
  {
    n: "01",
    eyebrow: "Connect",
    title: "Hook into your stack, or just paste.",
    body: "**Wire up** Datadog, Grafana, or New Relic with an API key. Or skip the integrations entirely: **paste raw logs**, **drop a file**, or fire a PagerDuty webhook. Works either way.",
    accent: "neutral" as const,
  },
  {
    n: "02",
    eyebrow: "Analyze",
    title: "Eight investigation tools, one structured verdict.",
    body: "The agent inventories services, correlates the timeline, traces back to **patient zero**, computes the **blast radius**, and hypothesizes the trigger. Then **Nova Pro** synthesizes a single coherent analysis with quoted evidence.",
    accent: "violet" as const,
  },
  {
    n: "03",
    eyebrow: "Triage",
    title: "Root cause and a fix, in under ten seconds.",
    body: "**Root cause** with confidence. A reconstructed **timeline** of the cascade. A severity verdict with reasoning. **Ranked fixes** with copy-paste snippets. A **post mortem PDF** ready for Confluence.",
    accent: "emerald" as const,
  },
];

const ACCENT_STYLES: Record<
  "neutral" | "violet" | "emerald",
  {
    badge: string;
    badgeRing: string;
    glow: string;
    eyebrow: string;
  }
> = {
  neutral: {
    badge: "bg-ink-950 text-ink-100 border-white/[0.12]",
    badgeRing: "ring-white/[0.10]",
    glow:
      "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(255, 255, 255, 0.05), transparent 70%)",
    eyebrow: "text-ink-300",
  },
  violet: {
    badge: "bg-ink-950 text-violet-100 border-violet-400/40",
    badgeRing: "ring-violet-500/20",
    glow:
      "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(139, 92, 246, 0.18), transparent 70%)",
    eyebrow: "text-violet-300",
  },
  emerald: {
    badge: "bg-ink-950 text-emerald-100 border-emerald-400/40",
    badgeRing: "ring-emerald-500/20",
    glow:
      "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(16, 185, 129, 0.15), transparent 70%)",
    eyebrow: "text-emerald-300",
  },
};

function HowItWorks() {
  return (
    <section className="border-t border-white/[0.05] bg-ink-950/60">
      <div className="mx-auto max-w-5xl px-6 py-32">
        <div className="text-center max-w-xl mx-auto">
          <div className="chip">How it works</div>
          <h2 className="mt-4 text-3xl md:text-4xl font-semibold tracking-tight text-ink-50">
            Three steps. Zero noise.
          </h2>
        </div>

        {/* Sequential step cards. Each is its own self-contained box with
            min-height so it owns a real chunk of scroll. As you scroll
            past one, the next animates in. */}
        <div className="mt-14 space-y-6">
          {STEP_PANELS.map((step) => (
            <StepPanel key={step.n} step={step} />
          ))}
        </div>
      </div>
    </section>
  );
}

function StepPanel({ step }: { step: (typeof STEP_PANELS)[number] }) {
  const accent = ACCENT_STYLES[step.accent];

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: false, amount: 0.4 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      className="relative rounded-3xl border border-white/[0.06] bg-ink-900/40 backdrop-blur-sm overflow-hidden"
    >
      {/* Accent glow inside the panel, contained by overflow-hidden so
          it can never leak past the border radius. */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ backgroundImage: accent.glow }}
      />

      <div className="relative grid md:grid-cols-[auto,1fr] gap-6 md:gap-10 p-7 md:p-10">
        {/* Number badge */}
        <div className="flex md:flex-col items-start gap-3">
          <span
            className={cn(
              "grid place-items-center size-14 rounded-full font-mono tabular-nums text-base border ring-4",
              accent.badge,
              accent.badgeRing,
            )}
          >
            {step.n}
          </span>
          <span
            className={cn(
              "text-[10.5px] uppercase tracking-[0.22em] font-semibold mt-2",
              accent.eyebrow,
            )}
          >
            {step.eyebrow}
          </span>
        </div>

        {/* Title + body */}
        <div className="min-w-0">
          <h3 className="text-[22px] md:text-[26px] font-semibold tracking-tight text-ink-50 leading-snug">
            {step.title}
          </h3>
          <div className="mt-3 text-[15px] md:text-[16px] text-ink-300 leading-relaxed">
            <ScrollRevealText
              dim={0.22}
              spread={0.9}
              emphasisClassName="text-ink-50 font-medium"
            >
              {step.body}
            </ScrollRevealText>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

