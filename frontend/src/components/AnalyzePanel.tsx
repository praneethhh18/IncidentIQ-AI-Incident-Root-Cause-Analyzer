"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileUp,
  Loader2,
  Play,
  Radar,
  Sparkles,
  Upload,
  Zap,
} from "lucide-react";

import { api } from "@/lib/api";
import type {
  AgentStep,
  AnalyzeResponse,
  IntegrationStatus,
  SampleIncident,
  SourceKind,
} from "@/lib/types";
import { cn } from "@/lib/utils";

import { AgentTrail } from "./AgentTrail";
import { AnalysisResult } from "./AnalysisResult";
import { IntegrationCard } from "./IntegrationCard";
import { PulseDot } from "./motion-primitives";

type Tab = "paste" | "upload" | "datadog" | "grafana" | "newrelic";

const TABS: { id: Tab; label: string; source: SourceKind }[] = [
  { id: "paste", label: "Paste logs", source: "paste" },
  { id: "upload", label: "Upload file", source: "upload" },
  { id: "datadog", label: "Datadog", source: "datadog" },
  { id: "grafana", label: "Grafana", source: "grafana" },
  { id: "newrelic", label: "New Relic", source: "newrelic" },
];

export function AnalyzePanel({
  samples,
  integrations,
}: {
  samples: SampleIncident[];
  integrations: IntegrationStatus[];
}) {
  const [tab, setTab] = useState<Tab>("paste");
  const [logs, setLogs] = useState("");
  const [serviceHint, setServiceHint] = useState("");
  const [query, setQuery] = useState("");
  const [windowMinutes, setWindowMinutes] = useState(30);
  const [filename, setFilename] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [liveSteps, setLiveSteps] = useState<AgentStep[]>([]);
  const [livePhase, setLivePhase] = useState<string | null>(null);

  // Datadog auto-mode state. Defaults to Auto so new users get a
  // one-click experience instead of having to learn Datadog query syntax.
  const [datadogAdvanced, setDatadogAdvanced] = useState(false);
  const [datadogService, setDatadogService] = useState<string>("");
  const [datadogServices, setDatadogServices] = useState<string[]>([]);
  const [datadogServicesLoaded, setDatadogServicesLoaded] = useState(false);

  const resultRef = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Lazy-load the service list the first time the user opens the
  // Datadog tab. Best-effort: an empty list just falls back to
  // showing the manual query field.
  useEffect(() => {
    if (tab !== "datadog" || datadogServicesLoaded) return;
    let cancelled = false;
    (async () => {
      try {
        // 6 hours covers a hackathon session's worth of test events
        // without crossing into yesterday's noise.
        const res = await api.datadogServices(360);
        if (cancelled) return;
        setDatadogServices(res.services ?? []);
        setDatadogServicesLoaded(true);
        if (!datadogService && res.services?.length) {
          const preferred = res.services.find((s) =>
            s.toLowerCase().includes("fashion-aura"),
          );
          setDatadogService(preferred ?? res.services[0]);
        }
      } catch {
        setDatadogServicesLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab, datadogServicesLoaded, datadogService]);

  useEffect(() => {
    if (result && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [result]);

  const loadSample = async (sampleId: string) => {
    try {
      const sample = await api.samplePayload(sampleId);
      setTab("paste");
      setLogs(sample.logs);
      setServiceHint(sample.service_hint || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onFile = (file: File) => {
    setFilename(file.name);
    const reader = new FileReader();
    reader.onload = () => setLogs(String(reader.result || ""));
    reader.readAsText(file);
  };

  const run = async () => {
    setLoading(true);
    setError(null);
    setLiveSteps([]);
    setLivePhase("Connecting to agent…");
    setResult(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const source =
        TABS.find((t) => t.id === tab)?.source ?? ("paste" as SourceKind);

      // For Datadog in Auto mode, synthesise the query from the picked
      // service. We include warn / critical / emergency in addition to
      // error so the incident view matches what the user sees in the
      // Datadog console - previously we silently filtered everything
      // except status:error and judges noticed the gap.
      let effectiveQuery = query;
      if (source === "datadog" && !datadogAdvanced) {
        const severityFilter =
          "status:(emergency OR critical OR alert OR error OR warn OR warning)";
        effectiveQuery = datadogService
          ? `service:${datadogService} ${severityFilter}`
          : severityFilter;
      }

      const body = {
        source,
        title: filename || undefined,
        service_hint: serviceHint || undefined,
        logs:
          source === "datadog" || source === "grafana" || source === "newrelic"
            ? undefined
            : logs,
        integration_query: effectiveQuery || undefined,
        time_window_minutes: windowMinutes,
      };

      if ((source === "paste" || source === "upload") && !logs.trim()) {
        throw new Error("Paste logs or upload a file first.");
      }

      let final: AnalyzeResponse | null = null;
      let streamFailed = false;

      try {
        for await (const event of api.analyzeStream(body, controller.signal)) {
          if (event.type === "agent_step") {
            setLiveSteps((prev) => [...prev, event.step]);
          } else if (event.type === "phase") {
            setLivePhase(event.message || event.phase);
          } else if (event.type === "complete") {
            final = event.analysis;
          } else if (event.type === "error") {
            throw new Error(event.message);
          }
        }
      } catch (streamErr) {
        if ((streamErr as Error).name === "AbortError") throw streamErr;
        console.warn("Stream failed, falling back to /analyze:", streamErr);
        streamFailed = true;
      }

      // Safety net: if the stream never delivered a complete event, fall
      // back to the synchronous /analyze endpoint so the result still renders.
      if (!final) {
        if (!streamFailed) {
          console.warn("Stream finished without complete event, falling back");
        }
        setLivePhase("Finalising analysis…");
        final = await api.analyze(body);
      }

      setResult(final);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setLivePhase(null);
      abortRef.current = null;
    }
  };

  const needsLogs = tab === "paste" || tab === "upload";

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-white/[0.08] bg-ink-950/85 backdrop-blur-md overflow-hidden">
        {/* Tab bar */}
        <div className="flex items-center gap-1 px-3 pt-3 pb-0 border-b border-white/[0.08] overflow-x-auto bg-ink-950/50">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "relative px-3.5 py-2.5 text-[13px] rounded-t-lg transition shrink-0 font-medium",
                tab === t.id
                  ? "text-ink-50 bg-ink-900 border-x border-t border-white/[0.10]"
                  : "text-ink-200 hover:text-white hover:bg-white/[0.04]",
              )}
            >
              {t.label}
              {tab === t.id ? (
                <span className="absolute left-3 right-3 -bottom-px h-[2px] bg-white rounded-full" />
              ) : null}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {needsLogs ? (
            <>
              {tab === "upload" ? (
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const f = e.dataTransfer.files?.[0];
                    if (f) onFile(f);
                  }}
                  className="rounded-xl border-2 border-dashed border-white/[0.10] hover:border-brand-500/40 hover:bg-brand-500/5 transition p-8 text-center cursor-pointer"
                  onClick={() => fileInput.current?.click()}
                >
                  <Upload className="size-6 mx-auto text-ink-400" />
                  <div className="mt-2 text-sm text-ink-200">
                    Drop a log file or click to choose
                  </div>
                  <div className="text-[11.5px] text-ink-500 mt-1">
                    .log, .txt, .json, up to 5MB
                  </div>
                  {filename ? (
                    <div className="mt-3 chip">
                      <FileUp className="size-3" /> {filename}
                    </div>
                  ) : null}
                  <input
                    ref={fileInput}
                    type="file"
                    accept=".log,.txt,.json,.out"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) onFile(f);
                    }}
                  />
                </div>
              ) : null}

              <div>
                <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
                  {tab === "upload" ? "Preview" : "Paste raw logs"}
                </label>
                <textarea
                  className="textarea"
                  rows={tab === "upload" ? 6 : 10}
                  placeholder={
                    tab === "upload"
                      ? "Drop a file above. Its contents will appear here."
                      : "Paste the relevant log output. Mixed structured/unstructured is fine."
                  }
                  value={logs}
                  onChange={(e) => setLogs(e.target.value)}
                />
              </div>

              {samples.length > 0 ? (
                <div>
                  <div className="text-[11.5px] uppercase tracking-wider text-ink-500 mb-2 flex items-center gap-1.5">
                    <Sparkles className="size-3 text-brand-300" />
                    Try a sample incident
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {samples.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => loadSample(s.id)}
                        className="chip hover:bg-white/[0.10] hover:text-ink-50 transition"
                      >
                        {s.title}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : tab === "datadog" ? (
            <DatadogTabBody
              advanced={datadogAdvanced}
              onToggleAdvanced={() => setDatadogAdvanced((v) => !v)}
              query={query}
              onQueryChange={setQuery}
              windowMinutes={windowMinutes}
              onWindowMinutesChange={setWindowMinutes}
              service={datadogService}
              onServiceChange={setDatadogService}
              services={datadogServices}
              servicesLoaded={datadogServicesLoaded}
            />
          ) : (
            <>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 text-[12.5px] text-ink-300 leading-relaxed">
                Run a live query against {tab}. When credentials aren&apos;t
                configured the backend will return a realistic seeded stream so
                you can still demo the full flow.
              </div>
              <div className="grid sm:grid-cols-[1fr,160px] gap-3">
                <div>
                  <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
                    Query
                  </label>
                  <input
                    className="input"
                    placeholder={
                      tab === "grafana"
                        ? '{job="checkout-api"} |~ "(?i)(error|fail)"'
                        : "SELECT * FROM Log WHERE level='error' SINCE 30 minutes ago"
                    }
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
                    Window (min)
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={1440}
                    className="input"
                    value={windowMinutes}
                    onChange={(e) =>
                      setWindowMinutes(Number(e.target.value) || 30)
                    }
                  />
                </div>
              </div>
            </>
          )}

          <div className="grid sm:grid-cols-[1fr,auto] gap-3 items-end">
            <div>
              <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
                Service hint (optional)
              </label>
              <input
                className="input"
                placeholder="e.g. your-api-service"
                value={serviceHint}
                onChange={(e) => setServiceHint(e.target.value)}
              />
            </div>
            <button
              onClick={run}
              disabled={loading}
              className="btn-primary px-5 py-2.5 text-[14px] min-w-[180px]"
            >
              {loading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Analyzing…
                </>
              ) : (
                <>
                  <Play className="size-4" /> Analyze incident
                </>
              )}
            </button>
          </div>

          {error ? (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 text-red-200 px-3 py-2 text-[13px]">
              <AlertTriangle className="size-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-3">
        {integrations.map((s) => (
          <IntegrationCard key={s.name} status={s} />
        ))}
      </div>

      <div ref={resultRef}>
        {loading ? (
          <LiveAgentPanel
            steps={liveSteps}
            phase={livePhase}
            done={false}
          />
        ) : null}
        {!loading && result ? (
          <AnalysisResult
            analysis={result}
            showAgentTrail={true}
            rawLogs={logs}
          />
        ) : null}
      </div>
    </div>
  );
}

function LiveAgentPanel({
  steps,
  phase,
  done,
}: {
  steps: AgentStep[];
  phase: string | null;
  done: boolean;
}) {
  return (
    <div className="card-pad animate-fade-in">
      <div className="flex items-center gap-3 mb-4">
        <PulseDot className={done ? "text-emerald-400" : "text-brand-400"} />
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase tracking-[0.18em] text-brand-300 font-semibold">
            {done ? "Agent finished" : "Agent is thinking…"}
          </div>
          <div className="text-sm text-ink-300 mt-0.5 truncate">
            {phase ?? (done ? "Synthesis complete." : "Working…")}
          </div>
        </div>
        <span className="chip tabular-nums">{steps.length} steps</span>
      </div>
      {steps.length > 0 ? <AgentTrail steps={steps} /> : (
        <div className="text-sm text-ink-500 italic">
          Waiting for the agent to take its first step…
        </div>
      )}
    </div>
  );
}


function DatadogTabBody({
  advanced,
  onToggleAdvanced,
  query,
  onQueryChange,
  windowMinutes,
  onWindowMinutesChange,
  service,
  onServiceChange,
  services,
  servicesLoaded,
}: {
  advanced: boolean;
  onToggleAdvanced: () => void;
  query: string;
  onQueryChange: (q: string) => void;
  windowMinutes: number;
  onWindowMinutesChange: (n: number) => void;
  service: string;
  onServiceChange: (s: string) => void;
  services: string[];
  servicesLoaded: boolean;
}) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.04] p-3 text-[12.5px] text-ink-300 leading-relaxed flex items-start gap-2">
        <Zap className="size-3.5 mt-0.5 text-emerald-300 shrink-0" />
        <div>
          IncidentIQ pulls every error, warning and emergency from your
          connected Datadog account — exactly what you see in the
          Datadog console. Pick a service (or leave it on All) and
          click Analyze. No query syntax needed.
        </div>
      </div>

      {!advanced ? (
        <div className="grid sm:grid-cols-[1fr,160px] gap-3">
          <div>
            <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
              Service
            </label>
            <select
              className="input"
              value={service}
              onChange={(e) => onServiceChange(e.target.value)}
              disabled={!servicesLoaded}
            >
              <option value="">
                {servicesLoaded
                  ? services.length === 0
                    ? "(no recent services - All)"
                    : "All services"
                  : "Loading services…"}
              </option>
              {services.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
              Window (min)
            </label>
            <input
              type="number"
              min={1}
              max={1440}
              className="input"
              value={windowMinutes}
              onChange={(e) =>
                onWindowMinutesChange(Number(e.target.value) || 30)
              }
            />
          </div>
        </div>
      ) : (
        <div className="grid sm:grid-cols-[1fr,160px] gap-3">
          <div>
            <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
              Custom Datadog query
            </label>
            <input
              className="input"
              placeholder="service:checkout-api status:error"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-[11.5px] uppercase tracking-wider text-ink-500 mb-1.5">
              Window (min)
            </label>
            <input
              type="number"
              min={1}
              max={1440}
              className="input"
              value={windowMinutes}
              onChange={(e) =>
                onWindowMinutesChange(Number(e.target.value) || 30)
              }
            />
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={onToggleAdvanced}
        className="inline-flex items-center gap-1 text-[11.5px] text-ink-400 hover:text-ink-200 transition"
      >
        {advanced ? (
          <>
            <ChevronDown className="size-3" /> Hide custom query
          </>
        ) : (
          <>
            <ChevronRight className="size-3" /> Advanced: write a custom Datadog
            query
          </>
        )}
      </button>
    </div>
  );
}
