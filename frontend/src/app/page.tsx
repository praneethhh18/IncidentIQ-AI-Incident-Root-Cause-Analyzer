"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Brain,
  Clock,
  FileDown,
  GitBranch,
  Microscope,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { EASE } from "@/lib/motion";
import {
  FadeIn,
  FadeItem,
  HoverCard,
  StaggerList,
} from "@/components/motion-primitives";

export default function Landing() {
  return (
    <>
      <Hero />
      <SocialProof />
      <Features />
      <HowItWorks />
      <CTA />
    </>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 bg-dots opacity-40 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" />
      <motion.div
        className="absolute -top-32 left-1/2 -translate-x-1/2 h-[28rem] w-[60rem] rounded-full bg-brand-500/20 blur-3xl"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1.2, ease: EASE }}
      />

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
          IncidentIQ reads your logs, traces the cascade back to patient zero, and writes the post mortem before your second coffee. Under 10 seconds.
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

function HeroPreview() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.7, ease: EASE, delay: 0.35 }}
      className="relative mx-auto max-w-6xl px-6 pb-20"
    >
      <div className="relative rounded-2xl border border-white/[0.07] bg-ink-900/60 backdrop-blur overflow-hidden shadow-glow">
        {/* Header bar: severity, incident id, duration */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-white/[0.05] bg-ink-900/80">
          <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10.5px] font-semibold text-sev-p1 bg-sev-p1/10 border border-sev-p1/25">
            <span className="size-1.5 rounded-full bg-sev-p1" />
            P1
          </span>
          <span className="font-mono text-[11px] text-ink-400 tabular-nums">
            INC-A4F12C9B
          </span>
          <span className="text-ink-700">·</span>
          <span className="text-[11.5px] text-ink-400 truncate">
            Cascading checkout failure
          </span>
          <span className="ml-auto font-mono text-[11px] text-ink-500 tabular-nums">
            3.1s
          </span>
        </div>

        <div className="grid md:grid-cols-[1.5fr,1fr] gap-0">
          {/* Left: analysis content */}
          <div className="p-7 border-b md:border-b-0 md:border-r border-white/[0.05]">
            <div className="text-[10.5px] uppercase tracking-[0.18em] text-ink-500 font-semibold">
              Root cause
            </div>
            <h3 className="mt-2 text-[22px] font-semibold tracking-tight text-ink-50 leading-snug">
              Postgres writer pool exhausted on checkout-api.
            </h3>
            <p className="mt-3 text-[13.5px] text-ink-400 leading-relaxed">
              A long-running query held connections past pool timeout,
              back-pressuring{" "}
              <span className="text-ink-200 font-medium">payments-worker</span>{" "}
              until Redis hit CLUSTERDOWN. Within 110 seconds the api-gateway
              tripped its circuit breaker. SLO burn 84x.
            </p>

            <div className="mt-6 grid grid-cols-3 gap-x-6 gap-y-1">
              <Stat label="Confidence" value="92%" />
              <Stat label="Services" value="5" />
              <Stat label="Blast radius" value="7" />
            </div>
          </div>

          {/* Right: timeline */}
          <div className="p-7 bg-ink-950/30">
            <div className="text-[10.5px] uppercase tracking-[0.18em] text-ink-500 font-semibold mb-4">
              Timeline
            </div>
            <ol className="relative space-y-3">
              <span className="absolute left-[3.95rem] top-1 bottom-1 w-px bg-white/[0.06]" />
              {[
                { t: "02:58:12", l: "DB pool pressure begins", s: "p3" },
                { t: "02:59:11", l: "Pool exhausted", s: "p2" },
                { t: "02:59:18", l: "Redis CLUSTERDOWN", s: "p1" },
                { t: "03:00:02", l: "Circuit breaker opens", s: "p1" },
                { t: "03:00:14", l: "payments-worker OOM", s: "p1" },
              ].map((event, i) => (
                <motion.li
                  key={event.t}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{
                    duration: 0.35,
                    ease: EASE,
                    delay: 0.65 + i * 0.08,
                  }}
                  className="relative grid grid-cols-[3.6rem,1rem,1fr] items-center gap-2 text-[12.5px]"
                >
                  <span className="font-mono text-[10.5px] text-ink-500 tabular-nums text-right">
                    {event.t}
                  </span>
                  <span className="grid place-items-center">
                    <span className={`sev-dot sev-dot-${event.s} ring-4 ring-ink-950`} />
                  </span>
                  <span className="text-ink-200 truncate">{event.l}</span>
                </motion.li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.16em] text-ink-500 font-semibold">
        {label}
      </div>
      <div className="text-[22px] font-semibold tracking-tight text-ink-50 tabular-nums mt-1">
        {value}
      </div>
    </div>
  );
}

function SocialProof() {
  const integrations = [
    "Datadog",
    "Grafana",
    "New Relic",
    "PagerDuty",
    "Opsgenie",
    "Slack",
  ];
  return (
    <section className="border-y border-white/[0.05] bg-ink-950/50">
      <div className="mx-auto max-w-7xl px-6 py-8 flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-ink-500">
        <span className="text-[11px] uppercase tracking-[0.2em]">
          Integrates with
        </span>
        {integrations.map((n) => (
          <span key={n} className="text-sm font-medium text-ink-300">
            {n}
          </span>
        ))}
      </div>
    </section>
  );
}

const FEATURES = [
  {
    icon: Microscope,
    title: "Forensic mode",
    body: "Trace the failure back to patient zero. Map the propagation path. See every service, dependency, and user segment caught in the blast radius.",
  },
  {
    icon: Brain,
    title: "Root cause in seconds",
    body: "The agent reads logs, traces, and alerts. It returns the single most likely cause with quoted evidence and a confidence score.",
  },
  {
    icon: Clock,
    title: "Timeline reconstruction",
    body: "Every event in chronological order. See when pressure started, when the cascade tripped, and when the breaker opened.",
  },
  {
    icon: Workflow,
    title: "Affected services map",
    body: "Service names pulled from your logs, classified by role, with a clear health verdict.",
  },
  {
    icon: ShieldCheck,
    title: "Explainable severity",
    body: "P1, P2, or P3 with reasoning. Not just a label. The agent tells you why this is a P1, in plain English.",
  },
  {
    icon: GitBranch,
    title: "Ranked fix recommendations",
    body: "Actionable steps with snippets you can paste straight into kubectl, psql, or your runbook.",
  },
  {
    icon: FileDown,
    title: "One-click post mortem",
    body: "Polished PDF ready to drop into Confluence or send to leadership. Generated alongside the analysis.",
  },
];

function Features() {
  return (
    <section className="mx-auto max-w-7xl px-6 py-24">
      <div className="max-w-2xl">
        <div className="chip">Why IncidentIQ</div>
        <h2 className="mt-4 text-3xl md:text-4xl font-semibold tracking-tight text-ink-50">
          Built like a senior SRE thinks.
        </h2>
        <p className="mt-3 text-ink-300">
          One root cause, not three. Quoted evidence, not hand-wavy guesses.
          Fixes with copy-paste snippets. The way you&apos;d want a calm 15-year
          on-call veteran to triage your pager at 3am.
        </p>
      </div>

      <StaggerList
        variant="staggerCards"
        className="mt-12 grid md:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <FadeItem key={title} variant="cardRise">
            <HoverCard className="card-pad h-full hover:border-white/[0.10] hover:bg-ink-900/60 transition-colors">
              <div className="size-9 grid place-items-center rounded-lg bg-white/[0.04] text-ink-100 border border-white/[0.08]">
                <Icon className="size-4" />
              </div>
              <h3 className="mt-4 font-semibold text-ink-50">{title}</h3>
              <p className="mt-1.5 text-sm text-ink-400 leading-relaxed">{body}</p>
            </HoverCard>
          </FadeItem>
        ))}
      </StaggerList>
    </section>
  );
}

const STEPS = [
  {
    n: "01",
    title: "Connect or paste",
    body: "Wire up Datadog, Grafana, or New Relic. Or just paste raw logs and drop a file. Works either way.",
  },
  {
    n: "02",
    title: "Analyze",
    body: "The agent runs eight investigation tools across the telemetry, then synthesises a structured analysis.",
  },
  {
    n: "03",
    title: "Triage in seconds",
    body: "Root cause, timeline, severity, affected services, ranked fixes, and a PDF post mortem.",
  },
];

function HowItWorks() {
  return (
    <section className="border-t border-white/[0.05] bg-ink-950/60">
      <div className="mx-auto max-w-7xl px-6 py-24 grid lg:grid-cols-[1fr,2fr] gap-12">
        <div>
          <div className="chip">How it works</div>
          <h2 className="mt-4 text-3xl md:text-4xl font-semibold tracking-tight text-ink-50">
            Three steps.<br />Zero noise.
          </h2>
          <p className="mt-3 text-ink-300">
            No agents to install. No log shipping to set up. IncidentIQ talks
            to your existing observability stack and gets out of the way.
          </p>
        </div>
        <ol className="space-y-4">
          {STEPS.map((s) => (
            <li key={s.n} className="card-pad flex gap-5">
              <div className="font-mono text-2xl text-ink-400 tabular-nums">
                {s.n}
              </div>
              <div>
                <div className="font-semibold text-ink-50">{s.title}</div>
                <div className="mt-1 text-sm text-ink-400 leading-relaxed">
                  {s.body}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="mx-auto max-w-5xl px-6 py-24 text-center">
      <div className="relative rounded-3xl border border-white/[0.06] bg-ink-900/40 p-12 overflow-hidden">
        <div className="relative">
          <h3 className="text-3xl md:text-4xl font-semibold tracking-tight text-ink-50">
            What took 2 hours now takes 10 seconds.
          </h3>
          <p className="mt-3 text-ink-400 max-w-xl mx-auto">
            Stop scrolling logs at 3am. Let the agent tell you what broke, why, and exactly how to fix it.
          </p>
          <div className="mt-7">
            <Link href="/dashboard" className="btn-primary px-5 py-2.5 text-[14px]">
              Open the dashboard
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
