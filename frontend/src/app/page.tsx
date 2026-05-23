"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Brain,
  Clock,
  FileDown,
  GitBranch,
  Layers,
  Microscope,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

import { EASE, transitions } from "@/lib/motion";
import {
  FadeIn,
  FadeItem,
  HoverCard,
  PulseDot,
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
        <FadeIn>
          <div className="inline-flex items-center gap-2 chip mb-6 text-brand-300">
            <PulseDot className="text-brand-400" />
            Powered by AWS Bedrock · Amazon Nova Pro
          </div>
        </FadeIn>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE, delay: 0.08 }}
          className="text-5xl md:text-6xl font-semibold tracking-tight text-ink-50 leading-[1.05]"
        >
          Find the{" "}
          <span className="bg-gradient-to-r from-brand-300 via-brand-200 to-white bg-clip-text text-transparent">
            root cause
          </span>
          <br />
          before the page bounces.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE, delay: 0.18 }}
          className="mt-6 max-w-2xl mx-auto text-ink-300 text-lg leading-relaxed"
        >
          IncidentIQ plugs into Datadog, Grafana, and New Relic, reads your logs in real time, and produces the root cause, timeline, affected services, severity, and a ranked fix list — in under 10 seconds.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE, delay: 0.28 }}
          className="mt-9 flex items-center justify-center gap-3"
        >
          <Link href="/dashboard" className="btn-primary px-5 py-2.5 text-[15px] group">
            <Sparkles className="size-4 transition group-hover:rotate-12" /> Try it now
            <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
          </Link>
          <Link href="/incidents" className="btn-secondary px-5 py-2.5 text-[15px]">
            View incidents
          </Link>
        </motion.div>

        <FadeIn delay={0.4}>
          <div className="mt-10 text-[12px] text-ink-500">
            Works out of the box — no keys required. Demo mode ships with three realistic incidents.
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
      <div className="relative rounded-3xl border border-white/[0.08] bg-gradient-to-b from-ink-900 to-ink-950 shadow-glow overflow-hidden">
        <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-white/[0.06] bg-ink-900/80">
          <span className="size-2.5 rounded-full bg-red-400/60" />
          <span className="size-2.5 rounded-full bg-amber-400/60" />
          <span className="size-2.5 rounded-full bg-emerald-400/60" />
          <span className="ml-3 text-[11px] text-ink-500 font-mono">
            incidentiq · INC-A4F12C9B
          </span>
        </div>
        <div className="grid md:grid-cols-5 gap-0">
          <div className="md:col-span-3 p-6 border-b md:border-b-0 md:border-r border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="chip bg-sev-p1/15 text-sev-p1 border-sev-p1/30">
                <span className="sev-dot sev-dot-p1" /> P1
              </span>
              <span className="chip">checkout-api · payments-worker · redis</span>
            </div>
            <h3 className="mt-3 text-2xl font-semibold tracking-tight text-ink-50">
              Cascading checkout failure — DB pool exhaustion → Redis cluster down
            </h3>
            <p className="mt-3 text-sm text-ink-300 leading-relaxed">
              Postgres writer pool exhausted on{" "}
              <span className="text-brand-300">checkout-api</span>, back-pressuring{" "}
              <span className="text-brand-300">payments-worker</span> until Redis
              hit CLUSTERDOWN. Within 110 seconds the api-gateway tripped its
              circuit breaker and SLO burn reached 84×.
            </p>

            <div className="mt-5 grid grid-cols-3 gap-3">
              <Stat label="Confidence" value="92%" />
              <Stat label="Services" value="5" />
              <Stat label="Analysis" value="3.1s" />
            </div>
          </div>
          <div className="md:col-span-2 p-6 space-y-3 bg-ink-950/40">
            <div className="text-[11px] uppercase tracking-wider text-ink-500">
              Timeline
            </div>
            {[
              { t: "02:58:12", l: "DB pool pressure begins", s: "p3" },
              { t: "02:59:11", l: "Pool exhausted", s: "p2" },
              { t: "02:59:18", l: "Redis CLUSTERDOWN", s: "p1" },
              { t: "03:00:02", l: "Circuit breaker opens", s: "p1" },
              { t: "03:00:14", l: "payments-worker OOM", s: "p1" },
            ].map((event, i) => (
              <motion.div
                key={event.t}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{
                  duration: 0.4,
                  ease: EASE,
                  delay: 0.65 + i * 0.1,
                }}
                className="flex items-start gap-3 text-sm"
              >
                <span className="font-mono text-[11px] text-ink-500 mt-1 tabular-nums">
                  {event.t}
                </span>
                <span className={`sev-dot mt-1.5 sev-dot-${event.s}`} />
                <span className="text-ink-200">{event.l}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-500">
        {label}
      </div>
      <div className="text-xl font-semibold tracking-tight text-ink-50 mt-0.5">
        {value}
      </div>
    </div>
  );
}

function SocialProof() {
  const integrations = ["Datadog", "Grafana", "New Relic", "AWS Bedrock", "Loki", "CloudWatch"];
  return (
    <section className="border-y border-white/[0.05] bg-ink-950/50">
      <div className="mx-auto max-w-7xl px-6 py-8 flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-ink-500">
        <span className="text-[11px] uppercase tracking-[0.2em]">Plays well with</span>
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
    title: "Forensic mode — reverse the cascade",
    body: "Trace the failure back to patient zero, map the full propagation path, and see every entity caught in the blast radius. Inspired by malware-forensic tooling.",
  },
  {
    icon: Brain,
    title: "Root cause in seconds",
    body: "AWS Bedrock (Nova Pro) reads logs, traces, and alerts — and returns the single most likely cause with quoted evidence and a confidence score.",
  },
  {
    icon: Clock,
    title: "Timeline reconstruction",
    body: "Every event in chronological order. See exactly when pressure started, when the cascade tripped, and when the breaker opened.",
  },
  {
    icon: Workflow,
    title: "Affected services map",
    body: "Service names pulled from your logs, classified by role, with a clear health verdict — healthy, degraded, or down.",
  },
  {
    icon: ShieldCheck,
    title: "Explainable severity",
    body: "P1 / P2 / P3 with reasoning. Not just a label — IncidentIQ tells you why this is a P1, in plain English.",
  },
  {
    icon: GitBranch,
    title: "Ranked fix recommendations",
    body: "Actionable steps with snippets you can paste straight into kubectl, psql, or your runbook.",
  },
  {
    icon: FileDown,
    title: "One-click PDF post-mortem",
    body: "Hand the report straight to leadership or drop it into Confluence. Ready to share before your coffee cools.",
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
            <HoverCard className="card-pad h-full hover:border-white/10 hover:bg-ink-900/80 transition-colors">
              <div className="size-9 grid place-items-center rounded-lg bg-brand-500/10 text-brand-300 border border-brand-500/20">
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
  { n: "01", title: "Connect or paste", body: "Wire up Datadog, Grafana, or New Relic — or just paste raw logs / drop a file. Works either way." },
  { n: "02", title: "Analyze", body: "IncidentIQ pipes the telemetry into Amazon Nova Pro with a prompt tuned for SRE-grade root-cause analysis." },
  { n: "03", title: "Triage in seconds", body: "Root cause, timeline, severity, affected services, ranked fixes. Plus a PDF for the post-mortem." },
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
              <div className="font-mono text-2xl text-brand-300/80 tabular-nums">
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
      <div className="relative rounded-3xl border border-white/[0.08] bg-gradient-to-br from-brand-500/15 via-ink-900 to-ink-900 p-12 overflow-hidden">
        <div className="absolute inset-0 bg-dots opacity-30" />
        <div className="relative">
          <div className="chip mx-auto mb-5">
            <Layers className="size-3.5" /> Production-grade SRE tooling
          </div>
          <h3 className="text-3xl md:text-4xl font-semibold tracking-tight text-ink-50">
            What took 2 hours now takes 10 seconds.
          </h3>
          <p className="mt-3 text-ink-300 max-w-xl mx-auto">
            Stop scrolling logs at 3am. Let IncidentIQ tell you what broke, why, and exactly how to fix it.
          </p>
          <div className="mt-7">
            <Link href="/dashboard" className="btn-primary px-5 py-2.5">
              <Sparkles className="size-4" /> Open the dashboard
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
