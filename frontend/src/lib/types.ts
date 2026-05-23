// Types mirror app/models/incident.py on the backend. Keep these in sync.

export type Severity = "P1" | "P2" | "P3";

export type SourceKind =
  | "paste"
  | "upload"
  | "datadog"
  | "grafana"
  | "newrelic"
  | "demo"
  | "webhook";

export interface AffectedService {
  name: string;
  role: string;
  impact: string;
  health: "healthy" | "degraded" | "down" | string;
}

export interface TimelineEvent {
  timestamp: string;
  label: string;
  detail: string;
  severity: Severity;
}

export interface FixRecommendation {
  title: string;
  rationale: string;
  action: string;
  snippet: string | null;
  priority: number;
}

export interface AgentStep {
  step: number;
  kind: "thought" | "tool_call" | "observation" | "decision" | string;
  title: string;
  detail: string;
  tool?: string | null;
  output?: unknown;
}

export interface BlastRadiusEntity {
  kind: "service" | "user_segment" | "region" | "dependency" | "data" | string;
  name: string;
  impact: string;
  severity: Severity | null;
}

export interface ForensicReport {
  patient_zero: TimelineEvent;
  propagation_path: string[];
  blast_radius: BlastRadiusEntity[];
  trigger_hypothesis: string;
  trigger_confidence: number;
  minutes_to_detection: number | null;
}

export interface AnalyzeResponse {
  incident_id: string;
  created_at: string;
  title: string;
  summary: string;
  root_cause: string;
  confidence: number;
  severity: Severity;
  severity_rationale: string;
  affected_services: AffectedService[];
  timeline: TimelineEvent[];
  fixes: FixRecommendation[];
  evidence: string[];
  source: SourceKind;
  model: string;
  duration_ms: number;
  agent_steps: AgentStep[];
  forensic: ForensicReport | null;
}

export interface IncidentSummary {
  incident_id: string;
  title: string;
  created_at: string;
  severity: Severity;
  root_cause: string;
  affected_service_count: number;
}

export interface IntegrationStatus {
  name: string;
  connected: boolean;
  enabled: boolean;
  detail: string;
}

export interface SampleIncident {
  id: string;
  title: string;
  service_hint: string;
}

export interface AnalyzeRequest {
  source: SourceKind;
  title?: string;
  logs?: string;
  service_hint?: string;
  integration_query?: string;
  time_window_minutes?: number;
}
