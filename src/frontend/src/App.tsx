import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ExternalLink,
  Loader2,
  Radio,
  RefreshCw,
  Search,
  X,
  Workflow
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type {
  EventRecord,
  RunCompletedMessage,
  RunErrorMessage,
  RunLaunchResponse,
  RunResponse,
  RunSnapshotMessage,
  RunStatus,
  RunStatusResponse,
  RunStreamMessage
} from "@/types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://multi-agent-prd-orchestrator.up.railway.app";

const FLOW_STEPS = [
  { step: "ingest_prd", label: "Intake" },
  { step: "plan_research_tasks", label: "Planning" },
  { step: "market_agent", label: "Market" },
  { step: "competitor_agent", label: "Competitor" },
  { step: "browser_agent", label: "Browser" },
  { step: "synthesize_plan", label: "Synthesis" },
  { step: "quality_gate", label: "Quality" },
  { step: "finalize", label: "Report" }
] as const;

const SAMPLE_PRD = `Build an AI meeting intelligence platform for mid-sized B2B SaaS companies.

The product should record, transcribe, summarize, and analyze customer calls from Zoom and Google Meet. It should automatically extract action items, objections, feature requests, and competitor mentions, then sync structured notes into Salesforce and HubSpot.

Target users:
- Sales managers
- Customer success teams
- Product managers

Core requirements:
- Call transcription and speaker separation
- AI-generated summaries and action items
- CRM sync for accounts, contacts, and notes
- Search across past calls
- Dashboard for trends in objections, requests, and competitor mentions
- Role-based access control
- SOC2-ready architecture

Business constraints:
- MVP in 10 weeks
- Team of 5 engineers
- Must support US English first
- Budget-conscious pricing strategy for mid-market customers

Success metrics:
- Reduce manual note-taking by 70%
- Improve CRM data completeness
- Increase visibility into customer pain points and competitor activity
`;

type Route =
  | { page: "home" }
  | { page: "run"; runId: string }
  | { page: "report"; runId: string };

function parseHash(hash: string): Route {
  if (!hash || hash === "#" || hash === "#/") {
    return { page: "home" };
  }

  const normalized = hash.replace(/^#/, "");
  const [path] = normalized.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "runs" && parts[1]) {
    if (parts[2] === "report") {
      return { page: "report", runId: decodeURIComponent(parts[1]) };
    }
    return { page: "run", runId: decodeURIComponent(parts[1]) };
  }

  return { page: "home" };
}

function navigate(route: Route) {
  if (route.page === "home") {
    window.location.hash = "/";
    return;
  }
  if (route.page === "report") {
    window.location.hash = `/runs/${encodeURIComponent(route.runId)}/report`;
    return;
  }
  window.location.hash = `/runs/${encodeURIComponent(route.runId)}`;
}

function toWebSocketUrl(runId: string) {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/runs/${runId}`;
  url.search = "";
  return url.toString();
}

function statusBadge(status: RunStatus | undefined) {
  if (status === "running") return <Badge variant="outline">running</Badge>;
  if (status === "success") return <Badge variant="success">success</Badge>;
  if (status === "degraded") return <Badge variant="warning">degraded</Badge>;
  if (status === "failed") return <Badge variant="danger">failed</Badge>;
  return <Badge variant="outline">unknown</Badge>;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function stringifyValue(value: unknown) {
  if (value == null) return "None";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function extractPreview(event: EventRecord) {
  const llmTrace = event.data.llm_trace as Record<string, unknown> | undefined;
  const preview =
    event.data.user_preview ??
    llmTrace?.output_text ??
    llmTrace?.output_preview ??
    event.data.raw_text ??
    event.data.raw_preview ??
    event.data.retry_raw_text ??
    event.data.retry_raw_preview;
  return typeof preview === "string" && preview.trim() ? preview : event.message;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function summarizeStepForUser(event?: EventRecord) {
  if (!event) {
    return "Waiting to start.";
  }

  if (typeof event.data.user_preview === "string" && event.data.user_preview.trim()) {
    return event.data.user_preview;
  }

  if (event.step === "ingest_prd") {
    return "The system received your PRD and started setting up the run.";
  }
  if (event.step === "plan_research_tasks") {
    return "The orchestrator is breaking your request into smaller research tasks for each specialist.";
  }
  if (event.step === "market_agent") {
    return "The market agent is checking demand, segments, and adoption signals.";
  }
  if (event.step === "competitor_agent") {
    return "The competitor agent is comparing alternatives, positioning, and pricing patterns.";
  }
  if (event.step === "browser_agent") {
    return "The browser agent is gathering public evidence from websites.";
  }
  if (event.step === "synthesize_plan") {
    return "The orchestrator is combining the agent outputs into a final plan.";
  }
  if (event.step === "quality_gate") {
    return "The system is validating whether the research quality is strong enough to trust.";
  }
  if (event.step === "finalize") {
    return "The final report is being packaged for display.";
  }
  return event.message;
}

function summarizeNodeHeadline(nodeId: string, latest?: EventRecord) {
  if (!latest) {
    return "Waiting for work.";
  }

  if (nodeId === "orchestrator") {
    if (latest.step === "plan_research_tasks") return "Organizing the work across agents.";
    if (latest.step === "synthesize_plan") return "Merging findings into one plan.";
    if (latest.step === "quality_gate") return "Reviewing quality and unresolved risks.";
    if (latest.step === "finalize") return "Preparing the final report.";
    return "Coordinating the workflow.";
  }

  if (nodeId === "market_agent") {
    return "Researching market demand and adoption signals.";
  }
  if (nodeId === "competitor_agent") {
    return "Comparing competing products and positioning.";
  }
  if (nodeId === "browser_agent") {
    return "Collecting public evidence from websites.";
  }

  return latest.message;
}

function summarizeNodeDetails(nodeId: string, latest?: EventRecord) {
  if (!latest) {
    return [];
  }

  const payload = asRecord(latest.data.payload);
  const rubric = asRecord(latest.data.rubric);
  const task = asRecord(latest.data.task);
  const details: string[] = [];

  if (nodeId === "orchestrator") {
    const requestSummary = latest.data.request_summary;
    if (typeof requestSummary === "string") {
      details.push(`Request summary: ${requestSummary}`);
    }
    const overall = latest.data.overall;
    if (typeof overall === "string") {
      details.push(`Current quality assessment: ${overall}.`);
    }
    const preview = extractPreview(latest);
    if (preview && preview !== latest.message) {
      details.push(preview);
    }
  }

  if (nodeId === "market_agent" && payload) {
    if (typeof payload.market_summary === "string") {
      details.push(payload.market_summary);
    }
    if (typeof payload.coverage === "number") {
      details.push(`Research coverage score: ${payload.coverage}/100.`);
    }
  }

  if (nodeId === "competitor_agent" && payload) {
    const competitors = Array.isArray(payload.competitors) ? payload.competitors : [];
    if (competitors.length > 0) {
      const names = competitors
        .map((item) => asRecord(item)?.name)
        .filter((item): item is string => typeof item === "string");
      if (names.length > 0) {
        details.push(`Compared ${names.join(", ")}.`);
      }
    }
    if (typeof payload.comparison_confidence === "number") {
      details.push(`Comparison confidence: ${payload.comparison_confidence}/100.`);
    }
  }

  if (nodeId === "browser_agent" && payload) {
    const facts = asStringArray(payload.facts);
    if (facts.length > 0) {
      details.push(`Evidence gathered: ${facts[0]}`);
    }
    if (typeof payload.url === "string") {
      details.push(`Primary source checked: ${payload.url}`);
    }
  }

  if (task?.title && typeof task.title === "string") {
    details.push(`Task: ${task.title}.`);
  }

  if (rubric?.score && typeof rubric.score === "number") {
    details.push(`Quality score: ${rubric.score}/100.`);
  }

  if (details.length === 0) {
    details.push(extractPreview(latest));
  }

  return details.slice(0, 4);
}

function summarizeEventForUser(event: EventRecord) {
  const payload = asRecord(event.data.payload);
  const task = asRecord(event.data.task);

  if (event.agent_id === "orchestrator") {
    return summarizeStepForUser(event);
  }

  if (task?.title && typeof task.title === "string") {
    return `${task.title}: ${extractPreview(event)}`;
  }

  if (payload) {
    if (typeof payload.market_summary === "string") return payload.market_summary;
    if (Array.isArray(payload.competitors) && payload.competitors.length > 0) return "Compared competitor options and positioning.";
    if (Array.isArray(payload.facts) && payload.facts.length > 0) return `Captured evidence: ${String(payload.facts[0])}`;
  }

  return extractPreview(event);
}

function readableCitations(value: unknown) {
  if (!Array.isArray(value) || value.length === 0) {
    return ["No citations attached to this node yet."];
  }

  return value.map((item) => {
    const citation = asRecord(item);
    if (!citation) {
      return "Citation available.";
    }
    const title = typeof citation.title === "string" ? citation.title : "Untitled source";
    const snippet = typeof citation.snippet === "string" ? citation.snippet : "";
    return snippet ? `${title}: ${snippet}` : title;
  });
}

function summarizeStepDetails(event?: EventRecord) {
  if (!event) {
    return ["This step has not started yet."];
  }

  const lines: string[] = [summarizeStepForUser(event)];
  const preview = extractPreview(event);
  if (preview && preview !== event.message) {
    lines.push(preview);
  }

  const task = asRecord(event.data.task);
  if (task && typeof task.title === "string") {
    lines.push(`Task in progress: ${task.title}.`);
  }

  const payload = asRecord(event.data.payload);
  if (payload) {
    if (typeof payload.market_summary === "string") {
      lines.push(payload.market_summary);
    }
    if (Array.isArray(payload.competitors) && payload.competitors.length > 0) {
      lines.push(`Competitors reviewed: ${payload.competitors.length}.`);
    }
    if (Array.isArray(payload.facts) && payload.facts.length > 0) {
      lines.push(`Evidence captured: ${String(payload.facts[0])}`);
    }
  }

  if (typeof event.data.overall === "string") {
    lines.push(`Quality status: ${event.data.overall}.`);
  }

  return lines.slice(0, 4);
}

function buildHighlightLines(event?: EventRecord) {
  if (!event) {
    return ["We have not collected any takeaways for this step yet."];
  }

  const payload = asRecord(event.data.payload);
  const task = asRecord(event.data.task);
  const lines: string[] = [];

  if (task && typeof task.title === "string") {
    lines.push(`Focus area: ${task.title}.`);
  }

  if (payload) {
    if (typeof payload.market_summary === "string") {
      lines.push(payload.market_summary);
    }
    const competitors = Array.isArray(payload.competitors) ? payload.competitors : [];
    if (competitors.length > 0) {
      const names = competitors
        .map((item) => asRecord(item)?.name)
        .filter((item): item is string => typeof item === "string");
      if (names.length > 0) {
        lines.push(`Products reviewed: ${names.join(", ")}.`);
      }
    }
    const facts = asStringArray(payload.facts);
    if (facts.length > 0) {
      lines.push(`Key evidence: ${facts[0]}`);
    }
    if (typeof payload.url === "string" && payload.url.trim()) {
      lines.push(`Source checked: ${payload.url}`);
    }
  }

  if (typeof event.data.overall === "string") {
    lines.push(`Result: ${event.data.overall}.`);
  }

  if (lines.length === 0) {
    lines.push("This step is in progress and more details will appear soon.");
  }

  return lines.slice(0, 4);
}

function buildActivityLines(events: EventRecord[]) {
  if (events.length === 0) {
    return ["This step has not started yet."];
  }

  return events.map((event) => {
    const statusLabel =
      event.event_type === "start"
        ? "Started"
        : event.event_type === "complete"
          ? "Completed"
          : event.event_type === "attempt"
            ? "Updated"
            : event.event_type === "error"
              ? "Needs attention"
              : "Updated";

    return `${formatTimestamp(event.created_at)} • ${statusLabel}`;
  });
}

function buildDetailedPreview(event?: EventRecord) {
  if (!event) {
    return "Nothing to preview yet.";
  }

  const llmTrace = asRecord(event.data.llm_trace);
  if (typeof llmTrace?.output_text === "string" && llmTrace.output_text.trim()) {
    return llmTrace.output_text;
  }

  if (typeof event.data.user_preview === "string" && event.data.user_preview.trim()) {
    return event.data.user_preview;
  }

  const payload = asRecord(event.data.payload);
  if (payload) {
    return stringifyValue(payload);
  }

  return extractPreview(event);
}

function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  const [prdText, setPrdText] = useState(SAMPLE_PRD);
  const [domain, setDomain] = useState("conversation-intelligence");
  const [runIdInput, setRunIdInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onHashChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  async function submitRun() {
    if (!prdText.trim()) {
      setError("PRD text is required.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/runs/launch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prd_text: prdText,
          domain: domain || undefined,
          constraints: []
        })
      });

      if (!response.ok) {
        throw new Error(`POST /runs/launch failed (${response.status})`);
      }

      const run = (await response.json()) as RunLaunchResponse;
      setRunIdInput(run.run_id);
      navigate({ page: "run", runId: run.run_id });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to launch run");
    } finally {
      setSubmitting(false);
    }
  }

  function openRun() {
    const trimmed = runIdInput.trim();
    if (!trimmed) {
      setError("Run ID is required.");
      return;
    }
    setError(null);
    navigate({ page: "run", runId: trimmed });
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_#fafaf9_0%,_#f8fafc_100%)] text-slate-900">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <header className="mb-8 flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">PRD Planner</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-950">Live Agent Flow</h1>
          </div>
          <div className="text-sm text-slate-500">
            {route.page === "home" ? "Submit" : `${route.page === "report" ? "Report" : "Run"} • ${route.runId}`}
          </div>
        </header>

        {error ? (
          <Card className="mb-6 border-red-200 bg-red-50">
            <CardContent className="p-4 text-sm text-red-700">{error}</CardContent>
          </Card>
        ) : null}

        {route.page === "home" ? (
          <HomeScreen
            prdText={prdText}
            domain={domain}
            runIdInput={runIdInput}
            submitting={submitting}
            onPrdChange={setPrdText}
            onDomainChange={setDomain}
            onRunIdChange={setRunIdInput}
            onSubmit={submitRun}
            onOpenRun={openRun}
          />
        ) : route.page === "report" ? (
          <ReportScreen route={route} onBack={() => navigate({ page: "run", runId: route.runId })} />
        ) : (
          <RunScreen
            route={route}
            onBack={() => navigate({ page: "home" })}
          />
        )}
      </div>
    </div>
  );
}

type HomeScreenProps = {
  prdText: string;
  domain: string;
  runIdInput: string;
  submitting: boolean;
  onPrdChange: (value: string) => void;
  onDomainChange: (value: string) => void;
  onRunIdChange: (value: string) => void;
  onSubmit: () => void;
  onOpenRun: () => void;
};

function HomeScreen(props: HomeScreenProps) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
      <Card className="border-slate-200 bg-white shadow-sm">
        <CardHeader>
          <Badge variant="outline" className="w-fit border-slate-200 bg-slate-50 text-slate-600">
            Product planning
          </Badge>
          <CardTitle className="text-3xl tracking-[-0.05em] text-slate-950">
            Turn your product idea into a clear plan.
          </CardTitle>
          <CardDescription className="max-w-2xl text-base leading-7 text-slate-600">
            Paste your product brief below. We will review the idea, explore the market, compare similar products, gather supporting evidence,
            and turn everything into a final recommendation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={props.prdText}
            onChange={(event) => props.onPrdChange(event.target.value)}
            className="min-h-56"
          />
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <Input
              value={props.domain}
              onChange={(event) => props.onDomainChange(event.target.value)}
              placeholder="domain (optional)"
            />
            <Button onClick={props.onSubmit} disabled={props.submitting}>
              {props.submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Workflow className="mr-2 h-4 w-4" />}
              Create Plan
            </Button>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-7 text-slate-600">
            You will be taken to a progress page where you can follow each step as the plan is prepared.
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Open saved plan</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={props.runIdInput}
              onChange={(event) => props.onRunIdChange(event.target.value)}
              placeholder="Enter plan ID"
            />
            <Button variant="secondary" className="w-full" onClick={props.onOpenRun}>
              <Search className="mr-2 h-4 w-4" />
              Open Plan
            </Button>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}

function RunScreen({ route, onBack }: { route: Extract<Route, { page: "run" }>; onBack: () => void }) {
  const [status, setStatus] = useState<RunStatusResponse | null>(null);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectionState, setConnectionState] = useState<"connecting" | "live" | "closed" | "error">("connecting");
  const [error, setError] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const refreshRun = useCallback(async () => {
    setError(null);
    try {
      const [statusRes, eventsRes] = await Promise.all([
        fetch(`${API_BASE}/runs/${route.runId}/status`),
        fetch(`${API_BASE}/runs/${route.runId}/events`)
      ]);

      if (!statusRes.ok) {
        throw new Error(`GET /runs/${route.runId}/status failed (${statusRes.status})`);
      }
      if (!eventsRes.ok) {
        throw new Error(`GET /runs/${route.runId}/events failed (${eventsRes.status})`);
      }

      const statusJson = (await statusRes.json()) as RunStatusResponse;
      const eventsJson = (await eventsRes.json()) as EventRecord[];
      setStatus(statusJson);
      setEvents(eventsJson);

      if (statusJson.status !== "running") {
        const runRes = await fetch(`${API_BASE}/runs/${route.runId}`);
        if (runRes.ok) {
          const runJson = (await runRes.json()) as RunResponse;
          setRun(runJson);
        }
        setLoading(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh run");
    }
  }, [route]);

  useEffect(() => {
    setError(null);
    setStatus(null);
    setRun(null);
    setEvents([]);
    setLoading(true);
    setConnectionState("connecting");
    setSelectedStep(null);

    const socket = new WebSocket(toWebSocketUrl(route.runId));
    socketRef.current = socket;

    socket.onopen = () => {
      setConnectionState("live");
    };

    socket.onmessage = (message) => {
      const payload = JSON.parse(message.data) as RunStreamMessage;
      if (payload.type === "snapshot") {
        const snapshot = payload as RunSnapshotMessage;
        setStatus(snapshot.status);
        setEvents(snapshot.events);
        setLoading(snapshot.status.status === "running");
        setConnectionState(snapshot.status.status === "running" ? "live" : "closed");
        return;
      }

      if (payload.type === "event") {
        setEvents((current) => [...current, payload.event]);
        return;
      }

      if (payload.type === "completed") {
        const completed = payload as RunCompletedMessage;
        setStatus(completed.status);
        setRun(completed.run);
        setLoading(false);
        setConnectionState("closed");
        return;
      }

      if (payload.type === "error") {
        const streamError = payload as RunErrorMessage;
        setError(streamError.message);
        setLoading(false);
        setConnectionState("error");
      }
    };

    socket.onerror = () => {
      setConnectionState("error");
    };

    socket.onclose = () => {
      setConnectionState((current) => (current === "error" ? current : "closed"));
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [route.runId]);

  useEffect(() => {
    if (status?.status !== "running" && !loading) {
      return;
    }

    void refreshRun();

    const intervalId = window.setInterval(() => {
      void refreshRun();
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [refreshRun, status?.status, loading]);

  const flowSteps = useMemo(
    () =>
      FLOW_STEPS.map((item) => ({
        ...item,
        event: events.find((entry) => entry.step === item.step)
      })),
    [events]
  );

  const activeStep = useMemo(() => {
    if (!events.length) {
      return loading ? "ingest_prd" : null;
    }
    if (run) {
      return null;
    }
    return events[events.length - 1]?.step ?? null;
  }, [events, loading, run]);

  const selectedStepIndex = useMemo(
    () => FLOW_STEPS.findIndex((item) => item.step === selectedStep),
    [selectedStep]
  );
  const selectedStepEvent = useMemo(
    () => (selectedStep ? events.filter((event) => event.step === selectedStep).slice(-1)[0] : undefined),
    [events, selectedStep]
  );
  const selectedStepTimeline = useMemo(
    () => (selectedStep ? events.filter((event) => event.step === selectedStep) : []),
    [events, selectedStep]
  );
  const selectedStepLabel = useMemo(
    () => FLOW_STEPS.find((item) => item.step === selectedStep)?.label ?? "",
    [selectedStep]
  );

  function openStep(stepId: string) {
    setSelectedStep(stepId);
  }

  function closeStep() {
    setSelectedStep(null);
  }

  function moveStep(direction: -1 | 1) {
    if (selectedStepIndex < 0) return;
    const nextIndex = selectedStepIndex + direction;
    if (nextIndex < 0 || nextIndex >= FLOW_STEPS.length) return;
    setSelectedStep(FLOW_STEPS[nextIndex].step);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Plan in progress</p>
            <h2 className="font-mono text-sm text-slate-900">{route.runId}</h2>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {statusBadge(status?.status)}
          <Button variant="secondary" onClick={() => navigate({ page: "report", runId: route.runId })} disabled={!run}>
            Open Report
          </Button>
          <Button variant="outline" onClick={refreshRun}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4 text-sm text-red-700">{error}</CardContent>
        </Card>
      ) : null}

      <Card className="border-slate-200 bg-white shadow-sm">
        <CardContent className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-900">Progress</p>
            <p className="mt-1 text-sm text-slate-600">
              {loading
                ? "We are working through your request now."
                : "Your plan is ready to review."}
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            {loading ? <Radio className="h-4 w-4 text-emerald-600" /> : <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
            {events.length} updates
          </div>
        </CardContent>
      </Card>

      {loading && events.length === 0 ? (
        <Card className="border-sky-200 bg-sky-50 shadow-sm">
          <CardContent className="flex items-center gap-3 p-4 text-sm text-sky-900">
            <Loader2 className="h-4 w-4 animate-spin" />
            Getting started. We are reading your brief and preparing the first step.
          </CardContent>
        </Card>
      ) : null}

      {connectionState === "error" && !error ? (
        <Card className="border-amber-200 bg-amber-50 shadow-sm">
          <CardContent className="p-4 text-sm text-amber-900">
            Live updates paused for a moment. We are still checking for progress in the background.
          </CardContent>
        </Card>
      ) : null}

      <section className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold tracking-[-0.03em] text-slate-950">Flow graph</h3>
          <p className="text-sm text-slate-600">
            Follow the journey from your brief to the final recommendation. The current step is highlighted, and completed steps turn green.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {flowSteps.map((item) => {
            const isDone = Boolean(item.event);
            const isCurrent = activeStep === item.step && !run;
            return (
              <Card
                key={item.step}
                className={cn(
                  "border shadow-sm transition-colors",
                  isDone && !isCurrent && "border-emerald-200 bg-emerald-50",
                  isCurrent && "border-sky-300 bg-sky-50 ring-2 ring-sky-200",
                  !isDone && !isCurrent && "border-slate-200 bg-white"
                )}
              >
                <button type="button" className="w-full text-left" onClick={() => openStep(item.step)}>
                  <CardContent className="p-4">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-slate-900">{item.label}</p>
                      <div className="flex items-center gap-2">
                        {isDone ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : isCurrent ? (
                          <Radio className="h-4 w-4 text-sky-600" />
                        ) : (
                          <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                        )}
                        <ChevronDown className="h-4 w-4 text-slate-400" />
                      </div>
                    </div>
                    <p className="text-xs leading-6 text-slate-500">
                      {summarizeStepForUser(item.event) || (isCurrent ? "Working here now..." : "Waiting...")}
                    </p>
                  </CardContent>
                </button>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold tracking-[-0.03em] text-slate-950">Final report</h3>
          <p className="text-sm text-slate-600">Open the full recommendation once everything is complete.</p>
        </div>

        {!run ? (
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardContent className="flex min-h-40 flex-col items-center justify-center gap-3 p-6 text-center">
              {loading ? <Loader2 className="h-7 w-7 animate-spin text-slate-400" /> : <Workflow className="h-7 w-7 text-slate-300" />}
              <p className="text-base font-medium text-slate-900">Your final plan is not ready yet</p>
              <p className="max-w-xl text-sm leading-7 text-slate-600">
                We are still reviewing the information. The final recommendation will appear here as soon as it is ready.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-base font-medium text-slate-900">Your final plan is ready</p>
                <p className="mt-1 text-sm text-slate-600">Open the report page to review the full recommendation and sources.</p>
              </div>
              <Button onClick={() => navigate({ page: "report", runId: route.runId })}>Open Final Plan</Button>
            </CardContent>
          </Card>
        )}
      </section>

      {selectedStep ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-8">
          <div className="relative flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_30px_80px_rgba(15,23,42,0.22)]">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Step details</p>
                <h3 className="mt-1 text-xl font-semibold tracking-[-0.03em] text-slate-950">{selectedStepLabel}</h3>
              </div>
              <button type="button" className="rounded-full p-2 text-slate-500 hover:bg-slate-100" onClick={closeStep}>
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid flex-1 gap-6 overflow-y-auto px-6 py-6 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="space-y-4">
                <NarrativePanel title="What is happening" lines={summarizeStepDetails(selectedStepEvent)} />
                <NarrativePanel
                  title="Timeline"
                  lines={
                    buildActivityLines(selectedStepTimeline)
                  }
                />
              </div>

              <div className="space-y-4">
                <NarrativePanel title="Key takeaways" lines={buildHighlightLines(selectedStepEvent)} />
                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="mb-3 text-sm font-medium text-slate-900">Detailed notes</p>
                  <div className="max-h-[320px] overflow-auto rounded-2xl bg-slate-50 p-4 text-sm leading-7 text-slate-700 whitespace-pre-wrap">
                    {buildDetailedPreview(selectedStepEvent)}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4">
              <Button variant="outline" onClick={() => moveStep(-1)} disabled={selectedStepIndex <= 0}>
                <ChevronLeft className="mr-2 h-4 w-4" />
                Previous
              </Button>
              <Button variant="outline" onClick={() => moveStep(1)} disabled={selectedStepIndex < 0 || selectedStepIndex >= FLOW_STEPS.length - 1}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ReportScreen({ route, onBack }: { route: Extract<Route, { page: "report" }>; onBack: () => void }) {
  const [run, setRun] = useState<RunResponse | null>(null);
  const [status, setStatus] = useState<RunStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadReport() {
      setLoading(true);
      setError(null);
      try {
        const [statusRes, runRes] = await Promise.all([
          fetch(`${API_BASE}/runs/${route.runId}/status`),
          fetch(`${API_BASE}/runs/${route.runId}`)
        ]);

        if (!statusRes.ok) {
          throw new Error(`GET /runs/${route.runId}/status failed (${statusRes.status})`);
        }

        const statusJson = (await statusRes.json()) as RunStatusResponse;
        if (cancelled) return;
        setStatus(statusJson);

        if (!runRes.ok) {
          if (statusJson.status === "running") {
            setRun(null);
            return;
          }
          throw new Error(`GET /runs/${route.runId} failed (${runRes.status})`);
        }

        const runJson = (await runRes.json()) as RunResponse;
        if (!cancelled) {
          setRun(runJson);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load report");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadReport();
    return () => {
      cancelled = true;
    };
  }, [route.runId]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Final plan</p>
            <h2 className="font-mono text-sm text-slate-900">{route.runId}</h2>
          </div>
        </div>
        {statusBadge(run?.status ?? status?.status)}
      </div>

      {error ? (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4 text-sm text-red-700">{error}</CardContent>
        </Card>
      ) : null}

      {!run ? (
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardContent className="flex min-h-56 flex-col items-center justify-center gap-3 p-6 text-center">
            {loading ? <Loader2 className="h-8 w-8 animate-spin text-slate-400" /> : <Workflow className="h-8 w-8 text-slate-300" />}
            <p className="text-base font-medium text-slate-900">Your plan is still being prepared</p>
            <p className="max-w-xl text-sm leading-7 text-slate-600">
              Please check back in a moment. You can return to the previous page to watch the progress.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardHeader>
              <CardTitle>Recommended plan</CardTitle>
              <CardDescription>Your final recommendation based on the research and analysis.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Intent</p>
                <p className="text-sm leading-7 text-slate-700">{run.execution_plan?.intent ?? "No intent available."}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Why this plan</p>
                <p className="text-sm leading-7 text-slate-700">{run.execution_plan?.explanation ?? "No explanation available."}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm leading-7 text-slate-700">{run.execution_plan?.summary ?? "No summary available."}</p>
              </div>
              {(run.execution_plan?.milestones ?? []).map((milestone) => (
                <div key={`${milestone.name}-${milestone.owner}`} className="rounded-2xl border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-slate-900">{milestone.name}</p>
                    <Badge variant="outline">{milestone.eta_days}d</Badge>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{milestone.description}</p>
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">{milestone.owner}</p>
                </div>
              ))}
            </CardContent>
          </Card>

            <div className="grid gap-4">
              <Card className="border-slate-200 bg-white shadow-sm">
                <CardHeader>
                  <CardTitle>Plan overview</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-4 py-3 text-sm">
                    <span className="text-slate-600">Status</span>
                    {statusBadge(run.status)}
                  </div>
                  {Object.entries(run.agent_scores).map(([agentId, score]) => (
                    <div key={agentId} className="flex items-center justify-between rounded-2xl border border-slate-200 px-4 py-3 text-sm">
                      <span className="text-slate-600">{agentId}</span>
                      <Badge variant="secondary">{score}</Badge>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card className="border-slate-200 bg-white shadow-sm">
                <CardHeader>
                  <CardTitle>Things to keep in mind</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2 text-sm text-slate-600">
                    {(run.unresolved_risks ?? []).map((risk) => (
                      <p key={risk}>• {risk}</p>
                    ))}
                    {run.unresolved_risks.length === 0 ? <p>No major concerns were flagged.</p> : null}
                  </div>

                  <div className="space-y-3">
                    {(run.citations ?? []).map((citation) => (
                      <a
                      key={citation.url}
                      href={citation.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-2xl border border-slate-200 p-4 text-sm text-sky-700 transition-colors hover:bg-slate-50"
                    >
                      {citation.url}
                    </a>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function NarrativePanel({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="mb-3 text-sm font-medium text-slate-900">{title}</p>
      <div className="max-h-64 overflow-y-auto space-y-2 pr-1 text-sm leading-7 text-slate-700">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
    </div>
  );
}

export default App;
