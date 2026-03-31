export type RunStatus = "running" | "success" | "degraded" | "failed";

export interface Citation {
  title: string;
  url: string;
  snippet?: string | null;
}

export interface Milestone {
  name: string;
  description: string;
  owner: string;
  eta_days: number;
}

export interface ExecutionPlan {
  intent: string;
  explanation: string;
  summary: string;
  milestones: Milestone[];
  risks: string[];
  dependencies: string[];
}

export interface RunResponse {
  run_id: string;
  trace_id: string;
  status: Exclude<RunStatus, "running">;
  execution_plan: ExecutionPlan | null;
  agent_scores: Record<string, number>;
  unresolved_risks: string[];
  citations: Citation[];
}

export interface RunLaunchResponse {
  run_id: string;
  trace_id: string;
  status: "running";
}

export interface RunStatusResponse {
  run_id: string;
  trace_id: string;
  status: RunStatus;
}

export interface EventRecord {
  run_id: string;
  trace_id: string;
  agent_id: string;
  step: string;
  event_type: string;
  message: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface RunRequestPayload {
  prd_text: string;
  domain?: string;
  constraints?: string[];
}

export interface RunEventMessage {
  type: "event";
  event: EventRecord;
}

export interface RunSnapshotMessage {
  type: "snapshot";
  status: RunStatusResponse;
  events: EventRecord[];
}

export interface RunCompletedMessage {
  type: "completed";
  status: RunStatusResponse;
  run: RunResponse | null;
}

export interface RunErrorMessage {
  type: "error";
  message: string;
}

export type RunStreamMessage = RunEventMessage | RunSnapshotMessage | RunCompletedMessage | RunErrorMessage;
