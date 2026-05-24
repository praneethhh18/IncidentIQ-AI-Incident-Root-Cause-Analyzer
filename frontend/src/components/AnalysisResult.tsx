"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  Clock,
  Cpu,
  FileDown,
  Hash,
  ScanSearch,
  Loader2,
} from "lucide-react";

import { api } from "@/lib/api";
import type { AnalyzeResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

import { AgentTrail } from "./AgentTrail";
import { CodeFixPanel } from "./CodeFixPanel";
import { DeepTraceBanner } from "./DeepTraceBanner";
import { DeepTracePanel } from "./DeepTracePanel";
import { EvidenceList } from "./EvidenceList";
import { FiveWhysCard } from "./FiveWhysCard";
import { FixRecommendations } from "./FixRecommendations";
import { ForensicReport } from "./ForensicReport";
import { IncidentChat } from "./IncidentChat";
import { IncidentRecheck } from "./IncidentRecheck";
import { IncidentTimeline } from "./IncidentTimeline";
import { BannerReveal, FadeItem, StaggerList } from "./motion-primitives";
import { RootCauseCard } from "./RootCauseCard";
import { ServiceGraph } from "./ServiceGraph";
import { SeverityBadge } from "./SeverityBadge";

export function AnalysisResult({
  analysis: initial,
  showAgentTrail = true,
  showOpenDetail = true,
  rawLogs,
}: {
  analysis: AnalyzeResponse;
  showAgentTrail?: boolean;
  /** Hide the "Open detail" link in the header (e.g. when already on the detail page). */
  showOpenDetail?: boolean;
  rawLogs?: string;
}) {
  const [analysis, setAnalysis] = useState<AnalyzeResponse>(initial);
  const [deepRunning, setDeepRunning] = useState(false);
  const [deepError, setDeepError] = useState<string | null>(null);

  const runDeepTrace = async (reason?: string) => {
    setDeepRunning(true);
    setDeepError(null);
    try {
      const updated = await api.deepTrace(analysis.incident_id, rawLogs, reason);
      setAnalysis(updated);
    } catch (err) {
      setDeepError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeepRunning(false);
    }
  };

  return (
    <StaggerList variant="staggerCards" className="space-y-5">
      <FadeItem variant="cardRise">
      <header className="card-pad">
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityBadge severity={analysis.severity} />
          <span className="chip">
            <Hash className="size-3" />
            {analysis.incident_id}
          </span>
          <span className="chip">
            <Clock className="size-3" />
            {formatDateTime(analysis.created_at)}
          </span>
          <span className="chip">
            <Cpu className="size-3" />
            {analysis.model}
          </span>
          {analysis.duration_ms > 0 ? (
            <span className="chip text-ink-400">
              analyzed in {(analysis.duration_ms / 1000).toFixed(1)}s
            </span>
          ) : null}
          <div className="sm:ml-auto flex items-center gap-2 flex-wrap">
            {!analysis.deep_trace ? (
              <button
                onClick={() => runDeepTrace("Manually invoked from analysis header.")}
                disabled={deepRunning || !rawLogs}
                title={
                  rawLogs
                    ? "Run the emergency deep-trace investigator"
                    : "Open the incident from the dashboard to enable deep trace"
                }
                className="btn px-3 py-1.5 text-[12.5px] bg-amber-500/10 text-amber-200 border border-amber-500/40 hover:bg-amber-500/20"
              >
                {deepRunning ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    Deep tracing…
                  </>
                ) : (
                  <>
                    <ScanSearch className="size-3.5" />
                    Run Deep Trace
                  </>
                )}
              </button>
            ) : null}
            <a
              href={api.exportPdfUrl(analysis.incident_id)}
              className="btn-secondary px-3 py-1.5 text-[12.5px]"
            >
              <FileDown className="size-3.5" /> Export PDF
            </a>
            {showOpenDetail ? (
              <Link
                href={`/incidents/${analysis.incident_id}`}
                className="btn-ghost px-3 py-1.5 text-[12.5px]"
              >
                Open detail <ArrowUpRight className="size-3.5" />
              </Link>
            ) : null}
          </div>
        </div>

        <h2 className="mt-4 text-xl sm:text-2xl font-semibold tracking-tight text-ink-50 break-words">
          {analysis.title}
        </h2>
        <p className="mt-3 text-[13.5px] sm:text-base text-ink-300 leading-relaxed break-words">
          {analysis.summary}
        </p>
      </header>
      </FadeItem>

      {analysis.should_escalate && !analysis.deep_trace ? (
        <BannerReveal>
          <DeepTraceBanner
            reason={analysis.escalation_reason}
            running={deepRunning}
            onRun={() => runDeepTrace(analysis.escalation_reason)}
          />
        </BannerReveal>
      ) : null}

      {deepError ? (
        <FadeItem>
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 text-red-200 px-3 py-2 text-[13px]">
            Deep Trace failed: {deepError}
          </div>
        </FadeItem>
      ) : null}

      {analysis.deep_trace ? (
        <BannerReveal>
          <DeepTracePanel report={analysis.deep_trace} />
        </BannerReveal>
      ) : null}

      <FadeItem variant="cardRise">
        <IncidentRecheck initial={analysis} rawLogs={rawLogs} />
      </FadeItem>


      <FadeItem>
        <div className="grid lg:grid-cols-2 gap-5">
          <RootCauseCard analysis={analysis} />
          <div className="card-pad">
            <h3 className="section-title mb-3">
              Affected services
            </h3>
            <ServiceGraph services={analysis.affected_services} />
          </div>
        </div>
      </FadeItem>

      {analysis.forensic ? (
        <FadeItem variant="cardRise">
          <ForensicReport forensic={analysis.forensic} />
        </FadeItem>
      ) : null}

      {analysis.five_whys ? (
        <FadeItem>
          <FiveWhysCard whys={analysis.five_whys} />
        </FadeItem>
      ) : null}

      <FadeItem>
        <div className="grid lg:grid-cols-[1.1fr,1fr] gap-5">
          <div className="card-pad">
            <h3 className="section-title mb-4">
              Incident timeline
            </h3>
            <IncidentTimeline events={analysis.timeline} />
          </div>
          <div className="card-pad">
            <h3 className="section-title mb-3">
              Fix recommendations
            </h3>
            <FixRecommendations fixes={analysis.fixes} />
          </div>
        </div>
      </FadeItem>

      <FadeItem>
        <div className="card-pad">
          <h3 className="section-title mb-3">
            Supporting evidence
          </h3>
          <EvidenceList lines={analysis.evidence} />
        </div>
      </FadeItem>

      <FadeItem variant="cardRise">
        <CodeFixPanel analysis={analysis} onUpdated={setAnalysis} />
      </FadeItem>

      <FadeItem variant="cardRise">
        <IncidentChat
          incidentId={analysis.incident_id}
          initialHistory={analysis.chat_history ?? []}
        />
      </FadeItem>

      {showAgentTrail && analysis.agent_steps && analysis.agent_steps.length > 0 ? (
        <FadeItem>
          <div className="card-pad">
            <div className="flex items-center gap-2 mb-1">
              <Bot className="size-4 text-brand-300" />
              <h3 className="section-title">
                Agent reasoning trail
              </h3>
              <span className="chip ml-auto">
                {analysis.agent_steps.length} steps
              </span>
            </div>
            <p className="text-[12.5px] text-ink-400 mb-4">
              How the agent thought, which tools it called, what it observed, and
              how it decided.
            </p>
            <AgentTrail steps={analysis.agent_steps} />
          </div>
        </FadeItem>
      ) : null}
    </StaggerList>
  );
}
