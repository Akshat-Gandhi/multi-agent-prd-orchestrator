from __future__ import annotations

import json
import os
import time
from typing import Any

from langchain_core.output_parsers import PydanticOutputParser

from prd_planner.agents.base import AgentContext
from prd_planner.agents.registry import AgentBundle, build_default_agents
from prd_planner.config.settings import settings
from prd_planner.contracts.schemas import (
    AgentError,
    ContractValidator,
    EventRecord,
    ExecutionPlan,
    Milestone,
    OrchestratorState,
    PlannerTask,
    PlannerTaskSet,
    QualityGateResult,
    RunRecord,
    RunRequest,
    RunResponse,
    TransferEnvelope,
)
from prd_planner.logging.json_logger import log_event
from prd_planner.models.provider import ModelRegistry, OllamaAdapter
from prd_planner.storage.sqlite_store import SQLiteStore

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - fallback for environments without langgraph
    END = "__end__"
    StateGraph = None


class Orchestrator:
    def __init__(
        self,
        store: SQLiteStore,
        model_registry: ModelRegistry | None = None,
        agents: AgentBundle | None = None,
    ) -> None:
        self.store = store
        self.model_registry = model_registry or ModelRegistry()
        self.agents = agents or build_default_agents()
        self.debug_llm_trace = os.getenv("DEBUG_LLM_TRACE", "false").lower() == "true"
        self.llm_trace_preview_chars = int(os.getenv("LLM_TRACE_PREVIEW_CHARS", "180"))

    def _persist_event(self, state: OrchestratorState, agent_id: str, step: str, event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        event = EventRecord(
            run_id=state.run.run_id,
            trace_id=state.run.trace_id,
            agent_id=agent_id,
            step=step,
            event_type=event_type,
            message=message,
            data=data or {},
        )
        self.store.save_event(event)
        log_event(event.model_dump())

    def _build_tasks(self, req: RunRequest) -> tuple[PlannerTaskSet, str, dict[str, Any] | None]:
        model = self.model_registry.get("planner", req.model_overrides.get("planner"))
        started = time.perf_counter()
        prefix = model.complete("create_research_tasks")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        planner_source = "ollama" if isinstance(model, OllamaAdapter) else "other"
        if isinstance(model, OllamaAdapter) and prefix.startswith("[ollama-fallback:"):
            planner_source = "ollama_fallback"
        llm_trace: dict[str, Any] | None = None
        if self.debug_llm_trace:
            model_name = getattr(model, "model", getattr(model, "name", "unknown"))
            llm_trace = {
                "model": model_name,
                "provider_source": planner_source,
                "latency_ms": elapsed_ms,
                "output_chars": len(prefix),
                "output_preview": prefix[: self.llm_trace_preview_chars],
            }
        domain = req.domain or "general"
        tasks = PlannerTaskSet(
            market_task=PlannerTask(
                title="Market scan",
                prompt=f"{prefix} Analyze market trends for {domain}. PRD: {req.prd_text[:300]}",
                desired_outputs=["market segments", "trends", "adoption signals"],
            ),
            competitor_task=PlannerTask(
                title="Competitor analysis",
                prompt=f"{prefix} Identify competitors and positioning for {domain}. PRD: {req.prd_text[:300]}",
                desired_outputs=["competitor list", "pricing", "feature matrix"],
            ),
            browser_task=PlannerTask(
                title="Browser evidence",
                prompt=f"{prefix} Open pages and capture public evidence for {domain} competitors.",
                desired_outputs=["facts", "supporting snippets"],
            ),
        )
        return tasks, planner_source, llm_trace

    def _validate_or_retry(self, state: OrchestratorState, key: str, envelope: TransferEnvelope) -> tuple[bool, list[str]]:
        validation = ContractValidator.validate_envelope(envelope.model_dump())
        reasons: list[str] = []
        if not validation.ok:
            reasons.extend(validation.errors)
        if envelope.rubric.score < settings.min_agent_score:
            reasons.append(f"score_below_threshold:{envelope.rubric.score}")
        if not reasons:
            return True, []
        if state.retries[key] < settings.max_retries_per_agent:
            state.retries[key] += 1
            return False, reasons
        return True, reasons

    def run(self, request: RunRequest) -> RunResponse:
        run = RunRecord(request=request)
        state = OrchestratorState(run=run)
        self.store.save_run(run)

        if StateGraph is None:
            final_state = self._run_sequential(state)
        else:
            graph = self._build_graph()
            final_data = graph.invoke({"state": state})
            final_state = final_data["state"]

        self.store.save_run(final_state.run)
        assert final_state.run.response is not None
        return final_state.run.response

    def _build_graph(self):
        graph = StateGraph(dict)
        graph.add_node("ingest_prd", self._node_ingest_prd)
        graph.add_node("plan_research_tasks", self._node_plan_research_tasks)
        graph.add_node("market_agent", self._node_market_agent)
        graph.add_node("competitor_agent", self._node_competitor_agent)
        graph.add_node("browser_agent", self._node_browser_agent)
        graph.add_node("synthesize_plan", self._node_synthesize_plan)
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("finalize", self._node_finalize)

        graph.set_entry_point("ingest_prd")
        graph.add_edge("ingest_prd", "plan_research_tasks")
        graph.add_edge("plan_research_tasks", "market_agent")
        graph.add_edge("market_agent", "competitor_agent")
        graph.add_edge("competitor_agent", "browser_agent")
        graph.add_edge("browser_agent", "synthesize_plan")
        graph.add_edge("synthesize_plan", "quality_gate")
        graph.add_edge("quality_gate", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _run_sequential(self, state: OrchestratorState) -> OrchestratorState:
        for fn in (
            self._node_ingest_prd,
            self._node_plan_research_tasks,
            self._node_market_agent,
            self._node_competitor_agent,
            self._node_browser_agent,
            self._node_synthesize_plan,
            self._node_quality_gate,
            self._node_finalize,
        ):
            data = fn({"state": state})
            state = data["state"]
        return state

    def _node_ingest_prd(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        self._persist_event(state, "orchestrator", "ingest_prd", "start", "Ingested PRD")
        return {"state": state}

    def _node_plan_research_tasks(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        state.tasks, planner_source, llm_trace = self._build_tasks(state.run.request)
        event_data: dict[str, Any] = {"planner_source": planner_source}
        if llm_trace is not None:
            event_data["llm_trace"] = llm_trace
        self._persist_event(
            state,
            "orchestrator",
            "plan_research_tasks",
            "complete",
            "Research tasks planned",
            event_data,
        )
        return {"state": state}

    def _run_agent_with_retry(self, state: OrchestratorState, key: str, agent, task: PlannerTask) -> TransferEnvelope:
        envelope: TransferEnvelope | None = None
        while True:
            context = AgentContext(
                run_id=state.run.run_id,
                trace_id=state.run.trace_id,
                task=task,
                prd_text=state.run.request.prd_text,
                domain=state.run.request.domain,
            )
            envelope = agent.run(context)
            done, reasons = self._validate_or_retry(state, key, envelope)
            self._persist_event(
                state,
                agent.id,
                f"{key}_agent",
                "attempt",
                "Agent execution completed",
                {"retry_count": state.retries[key], "reasons": reasons, "score": envelope.rubric.score},
            )
            if done:
                if reasons:
                    envelope.errors.extend([
                        AgentError(code="VALIDATION_OR_SCORE", message=r, retryable=False) for r in reasons
                    ])
                return envelope

    def _node_market_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        assert state.tasks is not None
        state.market_output = self._run_agent_with_retry(state, "market", self.agents.market, state.tasks.market_task)
        return {"state": state}

    def _node_competitor_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        assert state.tasks is not None
        state.competitor_output = self._run_agent_with_retry(state, "competitor", self.agents.competitor, state.tasks.competitor_task)
        return {"state": state}

    def _node_browser_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        assert state.tasks is not None
        state.browser_output = self._run_agent_with_retry(state, "browser", self.agents.browser, state.tasks.browser_task)
        return {"state": state}

    def _node_synthesize_plan(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        market = state.market_output.payload if state.market_output else {}
        competitors = state.competitor_output.payload if state.competitor_output else {}
        browser = state.browser_output.payload if state.browser_output else {}
        model = self.model_registry.get("planner", state.run.request.model_overrides.get("planner"))
        parser = PydanticOutputParser(pydantic_object=ExecutionPlan)
        format_instructions = parser.get_format_instructions()
        prompt = (
            "You are a product planning agent. Generate a production-ready execution plan.\n"
            "Return output using this exact formatting instruction:\n"
            f"{format_instructions}\n\n"
            "CRITICAL: Return a JSON INSTANCE, not a JSON schema.\n"
            "Your JSON MUST include these top-level keys only: summary, milestones, risks, dependencies.\n"
            "Do NOT output keys like: $defs, properties, required, title, type, items.\n"
            "milestones must be an array of objects with keys: name, description, owner, eta_days.\n"
            "eta_days must be an integer >= 1.\n"
            "Example valid shape:\n"
            "{\"summary\":\"...\",\"milestones\":[{\"name\":\"...\",\"description\":\"...\",\"owner\":\"...\",\"eta_days\":7}],\"risks\":[\"...\"],\"dependencies\":[\"...\"]}\n\n"
            f"PRD:\n{state.run.request.prd_text}\n\n"
            f"Domain: {state.run.request.domain or 'general'}\n"
            f"Constraints: {state.run.request.constraints}\n\n"
            f"Market payload: {json.dumps(market, ensure_ascii=True)}\n"
            f"Competitor payload: {json.dumps(competitors, ensure_ascii=True)}\n"
            f"Browser payload: {json.dumps(browser, ensure_ascii=True)}\n"
        )

        started = time.perf_counter()
        raw = model.complete(prompt)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            state.execution_plan = parser.parse(raw)
            event_data: dict[str, Any] = {"latency_ms": elapsed_ms, "status": "ok"}
            if self.debug_llm_trace:
                model_name = getattr(model, "model", getattr(model, "name", "unknown"))
                event_data["llm_trace"] = {
                    "model": model_name,
                    "output_chars": len(raw),
                    "output_preview": raw[: self.llm_trace_preview_chars],
                }
            self._persist_event(state, "orchestrator", "synthesize_plan", "complete", "Execution plan synthesized", event_data)
        except Exception as exc:
            # One strict retry: ask model to repair the prior output into a valid ExecutionPlan instance.
            repair_prompt = (
                "Fix the following output so it is a VALID JSON INSTANCE that satisfies the schema instructions.\n"
                "Return JSON only. Do not include markdown fences.\n\n"
                f"Schema instructions:\n{format_instructions}\n\n"
                f"Invalid output to repair:\n{raw}"
            )
            retry_started = time.perf_counter()
            repaired_raw = model.complete(repair_prompt)
            retry_elapsed_ms = int((time.perf_counter() - retry_started) * 1000)
            try:
                state.execution_plan = parser.parse(repaired_raw)
                event_data: dict[str, Any] = {
                    "latency_ms": elapsed_ms + retry_elapsed_ms,
                    "status": "ok_after_retry",
                    "retry": True,
                }
                if self.debug_llm_trace:
                    model_name = getattr(model, "model", getattr(model, "name", "unknown"))
                    event_data["llm_trace"] = {
                        "model": model_name,
                        "output_chars": len(repaired_raw),
                        "output_preview": repaired_raw[: self.llm_trace_preview_chars],
                    }
                self._persist_event(
                    state,
                    "orchestrator",
                    "synthesize_plan",
                    "complete",
                    "Execution plan synthesized after retry",
                    event_data,
                )
            except Exception as retry_exc:
                state.execution_plan = None
                self._persist_event(
                    state,
                    "orchestrator",
                    "synthesize_plan",
                    "error",
                    "Execution plan synthesis failed",
                    {
                        "error": str(retry_exc),
                        "first_error": str(exc),
                        "latency_ms": elapsed_ms + retry_elapsed_ms,
                        "raw_preview": raw[:200],
                        "retry_raw_preview": repaired_raw[:200],
                    },
                )
        return {"state": state}

    def _node_quality_gate(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        unresolved_risks: list[str] = []
        scores = {
            "market_agent": state.market_output.rubric.score if state.market_output else 0,
            "competitor_agent": state.competitor_output.rubric.score if state.competitor_output else 0,
            "browser_agent": state.browser_output.rubric.score if state.browser_output else 0,
        }
        for name, score in scores.items():
            if score < settings.min_agent_score:
                unresolved_risks.append(f"{name} score below threshold: {score}")
        if not state.execution_plan:
            unresolved_risks.append("execution plan missing")

        if not state.execution_plan:
            overall = "failed"
        elif unresolved_risks:
            overall = "degraded"
        else:
            overall = "success"

        state.quality_gate = QualityGateResult(
            passed=overall == "success",
            overall_status=overall,
            unresolved_risks=unresolved_risks,
        )
        self._persist_event(state, "orchestrator", "quality_gate", "complete", "Quality gate evaluated", {"overall": overall})
        return {"state": state}

    def _node_finalize(self, data: dict[str, Any]) -> dict[str, Any]:
        state: OrchestratorState = data["state"]
        citations = []
        for envelope in (state.market_output, state.competitor_output, state.browser_output):
            if envelope:
                citations.extend(envelope.citations)

        scores = {
            "market_agent": state.market_output.rubric.score if state.market_output else 0,
            "competitor_agent": state.competitor_output.rubric.score if state.competitor_output else 0,
            "browser_agent": state.browser_output.rubric.score if state.browser_output else 0,
        }

        status = state.quality_gate.overall_status if state.quality_gate else "failed"
        response = RunResponse(
            run_id=state.run.run_id,
            trace_id=state.run.trace_id,
            status=status,
            execution_plan=state.execution_plan,
            agent_scores=scores,
            unresolved_risks=state.quality_gate.unresolved_risks if state.quality_gate else ["quality gate missing"],
            citations=citations,
        )
        state.run.status = status
        state.run.response = response
        self._persist_event(state, "orchestrator", "finalize", "complete", "Run finalized", {"status": status})
        return {"state": state}
