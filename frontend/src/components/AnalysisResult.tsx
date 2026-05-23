import Link from "next/link";
import {
  ArrowUpRight,
  Bot,
  Clock,
  Cpu,
  FileDown,
  Hash,
} from "lucide-react";

import type { AnalyzeResponse } from "@/lib/types";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

import { AgentTrail } from "./AgentTrail";
import { EvidenceList } from "./EvidenceList";
import { FixRecommendations } from "./FixRecommendations";
import { ForensicReport } from "./ForensicReport";
import { IncidentTimeline } from "./IncidentTimeline";
import { RootCauseCard } from "./RootCauseCard";
import { ServiceGraph } from "./ServiceGraph";
import { SeverityBadge } from "./SeverityBadge";

export function AnalysisResult({
  analysis,
  showAgentTrail = true,
}: {
  analysis: AnalyzeResponse;
  showAgentTrail?: boolean;
}) {
  return (
    <div className="space-y-5 animate-fade-in">
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
          <div className="ml-auto flex items-center gap-2">
            <a
              href={api.exportPdfUrl(analysis.incident_id)}
              className="btn-secondary px-3 py-1.5 text-[12.5px]"
            >
              <FileDown className="size-3.5" /> Export PDF
            </a>
            <Link
              href={`/incidents/${analysis.incident_id}`}
              className="btn-ghost px-3 py-1.5 text-[12.5px]"
            >
              Open detail <ArrowUpRight className="size-3.5" />
            </Link>
          </div>
        </div>

        <h2 className="mt-4 text-2xl font-semibold tracking-tight text-ink-50">
          {analysis.title}
        </h2>
        <p className="mt-3 text-ink-300 leading-relaxed">{analysis.summary}</p>
      </header>

      <div className="grid lg:grid-cols-2 gap-5">
        <RootCauseCard analysis={analysis} />
        <div className="card-pad">
          <h3 className="text-sm font-semibold tracking-wide text-ink-50 uppercase mb-3">
            Affected services
          </h3>
          <ServiceGraph services={analysis.affected_services} />
        </div>
      </div>

      {analysis.forensic ? (
        <ForensicReport forensic={analysis.forensic} />
      ) : null}

      <div className="grid lg:grid-cols-[1.1fr,1fr] gap-5">
        <div className="card-pad">
          <h3 className="text-sm font-semibold tracking-wide text-ink-50 uppercase mb-4">
            Incident timeline
          </h3>
          <IncidentTimeline events={analysis.timeline} />
        </div>
        <div className="card-pad">
          <h3 className="text-sm font-semibold tracking-wide text-ink-50 uppercase mb-3">
            Fix recommendations
          </h3>
          <FixRecommendations fixes={analysis.fixes} />
        </div>
      </div>

      <div className="card-pad">
        <h3 className="text-sm font-semibold tracking-wide text-ink-50 uppercase mb-3">
          Supporting evidence
        </h3>
        <EvidenceList lines={analysis.evidence} />
      </div>

      {showAgentTrail && analysis.agent_steps && analysis.agent_steps.length > 0 ? (
        <div className="card-pad">
          <div className="flex items-center gap-2 mb-1">
            <Bot className="size-4 text-brand-300" />
            <h3 className="text-sm font-semibold tracking-wide text-ink-50 uppercase">
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
      ) : null}
    </div>
  );
}
