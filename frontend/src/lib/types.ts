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

export interface HiddenSignal {
  category:
    | "silent_failure"
    | "timing_anomaly"
    | "order_anomaly"
    | "service_silence"
    | "hidden_dependency"
    | string;
  title: string;
  detail: string;
  evidence: string[];
  severity: Severity | null;
}

export interface ServiceProbe {
  service: string;
  role: string;
  line_count: number;
  first_seen: string | null;
  last_seen: string | null;
  went_silent: boolean;
  error_burst_rate: number;
  findings: string[];
  suspected_role_in_cascade: "primary" | "propagator" | "bystander" | "sink" | string;
}

export interface DeepTraceReport {
  triggered_reason: string;
  auto_triggered: boolean;
  extended_model_used: string;
  duration_ms: number;
  hidden_signals: HiddenSignal[];
  service_probes: ServiceProbe[];
  expert_insights: string[];
  revised_root_cause: string;
  revised_confidence: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | string;
  content: string;
  timestamp: string;
}

export interface WhyStep {
  n: number;
  question: string;
  answer: string;
}

export interface FiveWhys {
  steps: WhyStep[];
  final_root_cause: string;
  counter_factual: string;
}

export interface WatchStatusPayload {
  running: boolean;
  started_at: string | null;
  last_polled_at: string | null;
  last_poll_log_lines: number;
  last_poll_summary: string;
  incidents_created: number;
  last_incident_id: string | null;
  last_error: string | null;
  poll_interval_s: number;
  window_minutes: number;
  error_threshold: number;
  service_filter: string | null;
}

export interface GitHubStatus {
  enabled: boolean;
  connected: boolean;
  login?: string;
  avatar_url?: string;
  scopes?: string;
  reason?: string;
}

export interface GitHubRepo {
  full_name: string;
  name: string;
  private: boolean;
  clone_url: string;
  default_branch: string;
  description: string;
  updated_at: string | null;
  language: string;
}

export interface CodeFixSubStep {
  name: string;
  summary: string;
  detail: string;
  duration_ms: number;
}

export interface CodeFix {
  repo_url: string;
  file_path: string;
  snippet: string;
  diff: string;
  rationale: string;
  confidence: number;
  verify_passed: boolean;
  verify_output: string;
  candidate_files: string[];
  sub_steps: CodeFixSubStep[];
  duration_ms: number;
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
  five_whys: FiveWhys | null;
  deep_trace: DeepTraceReport | null;
  should_escalate: boolean;
  escalation_reason: string;
  status: "open" | "investigating" | "recovering" | "resolved" | string;
  resolved_at: string | null;
  last_checked_at: string | null;
  recheck_count: number;
  resolution_summary: string;
  chat_history: ChatMessage[];
  code_fix?: CodeFix | null;
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
