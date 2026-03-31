import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Workflow
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { EventRecord, RunResponse } from "@/types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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

const SAMPLE_PRD =
  "Build a multi-agent planning console for product teams. The orchestrator should route the request to market, competitor, and browser agents, show their intermediate thinking and outputs, and then assemble a final report with milestones, risks, and citations.";

const DEMO_RUN: RunResponse = {
  run_id: "demo-run-step-1",
  trace_id: "demo-trace-step-1",
  status: "success",
  execution_plan: {
    summary:
      "Launch a minimal multi-agent console that clarifies the orchestration path first, then expand into interactive back-and-forth in step 2.",
    milestones: [
      {
        name: "Clean request flow",
        description: "Separate submission from run inspection so users understand where they are.",
        owner: "Frontend",
        eta_days: 2
      },
      {
        name: "Agent I/O visibility",
        description: "Show task input, agent payloads, and citations for each handoff.",
        owner: "Frontend + API",
        eta_days: 3
      }
    ],
    risks: ["No live socket or streaming yet.", "Progress only appears after the backend returns."],
    dependencies: ["FastAPI API", "SQLite event storage"]
  },
  agent_scores: {
    market_agent: 86,
    competitor_agent: 79,
    browser_agent: 85
  },
  unresolved_risks: ["Live event streaming is not implemented yet."],
  citations: [
    {
      title: "Example market evidence",
      url: "https://example.com/market",
      snippet: "Users need visible agent handoffs."
    }
  ]
};

const DEMO_EVENTS: EventRecord[] = [
  {
    run_id: DEMO_RUN.run_id,
    trace_id: DEMO_RUN.trace_id,
    agent_id: "orchestrator",
    step: "ingest_prd",
    event_type: "start",
    message: "PRD accepted by orchestrator.",
    data: {
      request_summary: "Create a UI that exposes orchestration flow and agent outputs."
    },
    created_at: "2026-03-31T09:30:00.000Z"
  },
  {
    run_id: DEMO_RUN.run_id,
    trace_id: DEMO_RUN.trace_id,
    agent_id: "orchestrator",
    step: "plan_research_tasks",
    event_type: "complete",
    message: "Tasks prepared for downstream agents.",
    data: {
      llm_trace: {
        output_preview: "Split work into market, competitor, browser, and synthesis passes."
      }
    },
    created_at: "2026-03-31T09:30:04.000Z"
  },
  {
    run_id: DEMO_RUN.run_id,
    trace_id: DEMO_RUN.trace_id,
    agent_id: "market_agent",
    step: "market_agent",
    event_type: "attempt",
    message: "Market scan complete.",
    data: {
      task: {
        title: "Market scan",
        prompt: "Analyze market trends for multi-agent-ui.",
        desired_outputs: ["market segments", "trends", "adoption signals"]
      },
      payload: {
        market_summary: "Transparent orchestration tooling is increasingly valuable for trust and debugging.",
        coverage: 92,
        source: "exa"
      },
      citations: [
        {
          title: "Example market evidence",
          url: "https://example.com/market",
          snippet: "Demand for traceable AI systems."
        }
      ],
      rubric: {
        score: 86,
        passed: true,
        unmet_criteria: [],
        notes: "source=exa"
      }
    },
    created_at: "2026-03-31T09:30:10.000Z"
  },
  {
    run_id: DEMO_RUN.run_id,
    trace_id: DEMO_RUN.trace_id,
    agent_id: "competitor_agent",
    step: "competitor_agent",
    event_type: "attempt",
    message: "Competitor pass complete.",
    data: {
      task: {
        title: "Competitor analysis",
        prompt: "Identify competitors and positioning for multi-agent-ui.",
        desired_outputs: ["competitor list", "pricing", "feature matrix"]
      },
      payload: {
        competitors: [
          { name: "Competitor A", positioning: "Workflow-first", pricing: "Tiered" },
          { name: "Competitor B", positioning: "Research-heavy", pricing: "Seat-based" }
        ],
        comparison_confidence: 79
      },
      rubric: {
        score: 79,
        passed: true,
        unmet_criteria: [],
        notes: "source=exa"
      }
    },
    created_at: "2026-03-31T09:30:18.000Z"
  },
  {
    run_id: DEMO_RUN.run_id,
    trace_id: DEMO_RUN.trace_id,
    agent_id: "browser_agent",
    step: "browser_agent",
    event_type: "attempt",
    message: "Browser evidence captured.",
    data: {
      task: {
        title: "Browser evidence",
        prompt: "Open pages and capture public evidence.",
        desired_outputs: ["facts", "supporting snippets"]
      },
      payload: {
        url: "https://example.com",
        facts: ["Auditability messaging is prominent.", "Visibility increases trust."]
      },
      rubric: {
        score: 85,
        passed: true,
        unmet_criteria: [],
        notes: "playwright_mcp_open_extract_close"
      }
    },
    created_at: "2026-03-31T09:30:27.000Z"
  },
  {
    run_id: DEMO_RUN.run_id,
    trace_id: DEMO_RUN.trace_id,
    agent_id: "orchestrator",
    step: "synthesize_plan",
    event_type: "complete",
    message: "Final report synthesized.",
    data: {
      llm_trace: {
        output_preview: "Merge agent outputs into a simple, product-facing planning report."
      }
    },
    created_at: "2026-03-31T09:30:33.000Z"
  },
  {
    run_id: DEMO_RUN.run_id,
    trace_id: DEMO_RUN.trace_id,
    agent_id: "orchestrator",
    step: "finalize",
    event_type: "complete",
    message: "Run finalized.",
    data: {
      status: "success"
    },
    created_at: "2026-03-31T09:30:40.000Z"
  }
];

type Route =
  | { page: "home" }
  | { page: "run"; runId: string; source: "live" | "demo" };

function parseHash(hash: string): Route {
  if (!hash || hash === "#" || hash === "#/") {
    return { page: "home" };
  }

  const normalized = hash.replace(/^#/, "");
  const [path, queryString] = normalized.split("?");
  const parts = path.split("/").filter(Boolean);

  if (parts[0] === "runs" && parts[1]) {
    const params = new URLSearchParams(queryString || "");
    const source = params.get("source") === "demo" ? "demo" : "live";
    return { page: "run", runId: decodeURIComponent(parts[1]), source };
  }

  return { page: "home" };
}

function navigate(route: Route) {
  if (route.page === "home") {
    window.location.hash = "/";
    return;
  }
  const query = route.source === "demo" ? "?source=demo" : "";
  window.location.hash = `/runs/${encodeURIComponent(route.runId)}${query}`;
}

function statusBadge(status?: RunResponse["status"]) {
  if (status === "success") return <Badge variant="success">success</Badge>;
  if (status === "degraded") return <Badge variant="warning">degraded</Badge>;
  if (status === "failed") return <Badge variant="danger">failed</Badge>;
  return <Badge variant="outline">idle</Badge>;
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
  const preview = llmTrace?.output_preview ?? event.data.raw_preview ?? event.data.retry_raw_preview;
  return typeof preview === "string" && preview.trim() ? preview : event.message;
}

function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  const [prdText, setPrdText] = useState(SAMPLE_PRD);
  const [domain, setDomain] = useState("multi-agent-ui");
  const [runIdInput, setRunIdInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);

  useEffect(() => {
    const onHashChange = () => {
      setRoute(parseHash(window.location.hash));
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (route.page !== "run") {
      return;
    }

    if (route.source === "demo") {
      setRun(DEMO_RUN);
      setEvents(DEMO_EVENTS);
      setLoadingRun(false);
      setError(null);
      return;
    }

    void loadRun(route.runId);
  }, [route]);

  async function loadRun(runId: string) {
    setLoadingRun(true);
    setError(null);
    try {
      const [runRes, eventsRes] = await Promise.all([
        fetch(`${API_BASE}/runs/${runId}`),
        fetch(`${API_BASE}/runs/${runId}/events`)
      ]);

      if (!runRes.ok) {
        throw new Error(`GET /runs/${runId} failed (${runRes.status})`);
      }
      if (!eventsRes.ok) {
        throw new Error(`GET /runs/${runId}/events failed (${eventsRes.status})`);
      }

      const runJson = (await runRes.json()) as RunResponse;
      const eventsJson = (await eventsRes.json()) as EventRecord[];
      setRun(runJson);
      setEvents(eventsJson);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run");
      setRun(null);
      setEvents([]);
    } finally {
      setLoadingRun(false);
    }
  }

  async function submitRun() {
    if (!prdText.trim()) {
      setError("PRD text is required.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prd_text: prdText,
          domain: domain || undefined,
          constraints: []
        })
      });

      if (!response.ok) {
        throw new Error(`POST /runs failed (${response.status})`);
      }

      const createdRun = (await response.json()) as RunResponse;
      setRunIdInput(createdRun.run_id);
      navigate({ page: "run", runId: createdRun.run_id, source: "live" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setSubmitting(false);
    }
  }

  function openExistingRun() {
    const trimmed = runIdInput.trim();
    if (!trimmed) {
      setError("Run ID is required.");
      return;
    }

    setError(null);
    navigate({ page: "run", runId: trimmed, source: "live" });
  }

  function openDemo() {
    setError(null);
    navigate({ page: "run", runId: DEMO_RUN.run_id, source: "demo" });
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,_#f8fafc_0%,_#f3f4f6_100%)] text-slate-900">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <TopBar route={route} />

        {error ? (
          <Card className="mb-6 border-red-200 bg-red-50">
            <CardContent className="p-4 text-sm text-red-700">{error}</CardContent>
          </Card>
        ) : null}

        {route.page === "home" ? (
          <HomePage
            prdText={prdText}
            domain={domain}
            runIdInput={runIdInput}
            submitting={submitting}
            onPrdChange={setPrdText}
            onDomainChange={setDomain}
            onRunIdChange={setRunIdInput}
            onSubmit={submitRun}
            onOpenExisting={openExistingRun}
            onOpenDemo={openDemo}
          />
        ) : (
          <RunPage
            runId={route.runId}
            loading={loadingRun || submitting}
            run={run}
            events={events}
            source={route.source}
            onBack={() => navigate({ page: "home" })}
            onRefresh={() => loadRun(route.runId)}
          />
        )}
      </div>
    </div>
  );
}

function TopBar({ route }: { route: Route }) {
  return (
    <header className="mb-8 flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">PRD Planner</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-950">Agent Flow Console</h1>
      </div>
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <span>{route.page === "home" ? "Home" : "Run details"}</span>
        <ChevronRight className="h-4 w-4" />
        <span className="text-slate-900">{route.page === "home" ? "Submit" : route.runId}</span>
      </div>
    </header>
  );
}

type HomePageProps = {
  prdText: string;
  domain: string;
  runIdInput: string;
  submitting: boolean;
  onPrdChange: (value: string) => void;
  onDomainChange: (value: string) => void;
  onRunIdChange: (value: string) => void;
  onSubmit: () => void;
  onOpenExisting: () => void;
  onOpenDemo: () => void;
};

function HomePage(props: HomePageProps) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <div className="space-y-6">
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <Badge variant="outline" className="w-fit border-slate-200 bg-slate-50 text-slate-600">
              Minimal step 1
            </Badge>
            <CardTitle className="text-3xl tracking-[-0.05em] text-slate-950">
              Submit a request, then inspect the run on a separate page.
            </CardTitle>
            <CardDescription className="max-w-2xl text-base leading-7 text-slate-600">
              The current backend is synchronous. There is no socket or live stream yet, so the UI only receives the full result after the API
              responds. This version keeps that honest and easy to follow.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              value={props.prdText}
              onChange={(event) => props.onPrdChange(event.target.value)}
              className="min-h-52"
              placeholder="Paste your PRD here..."
            />
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <Input
                value={props.domain}
                onChange={(event) => props.onDomainChange(event.target.value)}
                placeholder="domain (optional)"
              />
              <Button onClick={props.onSubmit} disabled={props.submitting}>
                {props.submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Workflow className="mr-2 h-4 w-4" />}
                Submit Request
              </Button>
            </div>
            {props.submitting ? (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                Waiting for the backend to finish the full orchestration. Because there is no live connection yet, this page will only move to
                run details once the API returns `200 OK`.
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-3">
          <MiniStat title="Pages" value="2" />
          <MiniStat title="Live stream" value="No" />
          <MiniStat title="Run history" value="Fetch by ID" />
        </div>
      </div>

      <div className="space-y-6">
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Open Existing Run</CardTitle>
            <CardDescription>Use a run ID to load the dedicated details page.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={props.runIdInput}
              onChange={(event) => props.onRunIdChange(event.target.value)}
              placeholder="run_id"
            />
            <Button variant="secondary" className="w-full" onClick={props.onOpenExisting}>
              <Search className="mr-2 h-4 w-4" />
              Open Run
            </Button>
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Preview the UI</CardTitle>
            <CardDescription>Open a clean demo run if you want to inspect the layout without calling the API.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" className="w-full" onClick={props.onOpenDemo}>
              <Sparkles className="mr-2 h-4 w-4" />
              Open Demo Run
            </Button>
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-slate-50 shadow-none">
          <CardContent className="p-5 text-sm leading-7 text-slate-600">
            Step 2 should introduce a live channel or async orchestration model. Until then, the cleanest UX is a clear submit screen followed
            by a dedicated results page.
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

type RunPageProps = {
  runId: string;
  source: "live" | "demo";
  loading: boolean;
  run: RunResponse | null;
  events: EventRecord[];
  onBack: () => void;
  onRefresh: () => void;
};

function RunPage(props: RunPageProps) {
  const stepEvents = useMemo(
    () =>
      FLOW_STEPS.map((item) => ({
        ...item,
        event: props.events.find((entry) => entry.step === item.step)
      })),
    [props.events]
  );

  const agentEvents = useMemo(
    () => props.events.filter((event) => event.agent_id !== "orchestrator"),
    [props.events]
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={props.onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{props.source === "demo" ? "Demo run" : "Live run"}</p>
            <h2 className="font-mono text-sm text-slate-900">{props.runId}</h2>
          </div>
        </div>
        {props.source === "live" ? (
          <Button variant="outline" onClick={props.onRefresh} disabled={props.loading}>
            <RefreshCw className={cn("mr-2 h-4 w-4", props.loading && "animate-spin")} />
            Refresh
          </Button>
        ) : null}
      </div>

      <Card className="border-slate-200 bg-white shadow-sm">
        <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-900">Run status</p>
            <p className="mt-1 text-sm text-slate-600">
              {props.loading
                ? "Waiting for response from the current backend."
                : "The backend has completed, so the UI can now display the captured run data."}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {props.run ? statusBadge(props.run.status) : <Badge variant="outline">loading</Badge>}
            <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-600">
              {props.events.length} events
            </Badge>
          </div>
        </CardContent>
      </Card>

      {props.loading ? (
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardContent className="flex min-h-64 flex-col items-center justify-center gap-3 p-6 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            <p className="text-base font-medium text-slate-900">Waiting for orchestration to finish</p>
            <p className="max-w-xl text-sm leading-7 text-slate-600">
              There is no WebSocket or server-sent stream in the current system. Progress becomes visible only after the request completes and
              the run details page can fetch the stored events.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {!props.loading && props.run ? (
        <>
          <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <Card className="border-slate-200 bg-white shadow-sm">
              <CardHeader>
                <CardTitle>Flow</CardTitle>
                <CardDescription>Minimal step tracker for the orchestration path.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {stepEvents.map((item, index) => (
                    <div key={item.step} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-900">{item.label}</p>
                        {item.event ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : (
                          <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                        )}
                      </div>
                      <p className="text-xs text-slate-500">{item.event?.message ?? "No event recorded"}</p>
                      {index < stepEvents.length - 1 ? <ArrowRight className="mt-3 h-4 w-4 text-slate-300" /> : null}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-200 bg-white shadow-sm">
              <CardHeader>
                <CardTitle>Report Snapshot</CardTitle>
                <CardDescription>High-level summary from the completed run.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm leading-7 text-slate-700">{props.run.execution_plan?.summary ?? "No summary available."}</p>
                </div>
                <div className="space-y-2">
                  {Object.entries(props.run.agent_scores).map(([agentId, score]) => (
                    <div key={agentId} className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2 text-sm">
                      <span className="text-slate-600">{agentId}</span>
                      <Badge variant="secondary">{score}</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>

          <Tabs defaultValue="agents">
            <TabsList className="bg-slate-100">
              <TabsTrigger value="agents">Agent I/O</TabsTrigger>
              <TabsTrigger value="report">Final report</TabsTrigger>
              <TabsTrigger value="events">All events</TabsTrigger>
            </TabsList>

            <TabsContent value="agents">
              <div className="space-y-4">
                {agentEvents.length === 0 ? (
                  <Card className="border-slate-200 bg-white shadow-sm">
                    <CardContent className="p-6 text-sm text-slate-600">No agent events are available for this run.</CardContent>
                  </Card>
                ) : null}

                {agentEvents.map((event, index) => (
                  <Card key={`${event.agent_id}-${event.created_at}-${index}`} className="border-slate-200 bg-white shadow-sm">
                    <CardHeader>
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Bot className="h-4 w-4 text-slate-500" />
                          <CardTitle className="text-base">{event.agent_id}</CardTitle>
                        </div>
                        <span className="text-xs text-slate-500">{formatTimestamp(event.created_at)}</span>
                      </div>
                      <CardDescription>{event.message}</CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4 lg:grid-cols-2">
                      <InfoBlock title="Input task" value={event.data.task} />
                      <InfoBlock title="Output payload" value={event.data.payload ?? event.data} />
                      <InfoBlock title="Rubric" value={event.data.rubric} />
                      <InfoBlock title="Citations" value={event.data.citations} />
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="report">
              <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
                <Card className="border-slate-200 bg-white shadow-sm">
                  <CardHeader>
                    <CardTitle>Execution plan</CardTitle>
                    <CardDescription>The final report produced by the current system.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm leading-7 text-slate-700">{props.run.execution_plan?.summary ?? "No summary available."}</p>
                    </div>
                    {(props.run.execution_plan?.milestones ?? []).map((milestone) => (
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
                      <CardTitle>Risks</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm text-slate-600">
                      {(props.run.unresolved_risks ?? []).map((risk) => (
                        <p key={risk}>• {risk}</p>
                      ))}
                      {props.run.unresolved_risks.length === 0 ? <p>No unresolved risks.</p> : null}
                    </CardContent>
                  </Card>

                  <Card className="border-slate-200 bg-white shadow-sm">
                    <CardHeader>
                      <CardTitle>Citations</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {(props.run.citations ?? []).map((citation) => (
                        <a
                          key={`${citation.title}-${citation.url}`}
                          href={citation.url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-start justify-between gap-3 rounded-2xl border border-slate-200 p-4 transition-colors hover:bg-slate-50"
                        >
                          <div>
                            <p className="font-medium text-slate-900">{citation.title}</p>
                            <p className="mt-1 text-xs text-slate-500">{citation.snippet}</p>
                          </div>
                          <ExternalLink className="mt-1 h-4 w-4 shrink-0 text-slate-400" />
                        </a>
                      ))}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="events">
              <div className="space-y-4">
                {props.events.map((event, index) => (
                  <Card key={`${event.step}-${event.created_at}-${index}`} className="border-slate-200 bg-white shadow-sm">
                    <CardHeader>
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{event.agent_id}</Badge>
                          <CardTitle className="text-base">
                            {event.step} • {event.event_type}
                          </CardTitle>
                        </div>
                        <span className="text-xs text-slate-500">{formatTimestamp(event.created_at)}</span>
                      </div>
                      <CardDescription>{extractPreview(event)}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <pre className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700">
                        {stringifyValue(event.data)}
                      </pre>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </div>
  );
}

function InfoBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-900">
        <FileText className="h-4 w-4 text-slate-400" />
        {title}
      </p>
      <pre className="text-xs text-slate-700">{stringifyValue(value)}</pre>
    </div>
  );
}

function MiniStat({ title, value }: { title: string; value: string }) {
  return (
    <Card className="border-slate-200 bg-white shadow-sm">
      <CardContent className="p-4">
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{title}</p>
        <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-950">{value}</p>
      </CardContent>
    </Card>
  );
}

export default App;
