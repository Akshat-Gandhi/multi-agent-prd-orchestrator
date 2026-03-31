from dataclasses import dataclass

from prd_planner.agents.base import AgentContext
from prd_planner.agents.registry import AgentBundle, build_default_agents
from prd_planner.config.settings import settings
from prd_planner.contracts.schemas import RubricResult, RunRequest, TransferEnvelope
from prd_planner.graph.orchestrator import Orchestrator
from prd_planner.models.provider import LLMManager, ModelRegistry
from prd_planner.storage.sqlite_store import SQLiteStore


@dataclass
class LowScoreMarketAgent:
    id: str = "market_agent"

    def run(self, context: AgentContext) -> TransferEnvelope:
        return TransferEnvelope(
            run_id=context.run_id,
            trace_id=context.trace_id,
            producer_agent=self.id,
            payload={"market_summary": "weak"},
            rubric=RubricResult(score=40, passed=False, unmet_criteria=["coverage"]),
        )


def make_request() -> RunRequest:
    return RunRequest(
        prd_text="Build an AI copilot for legal contract review for small law firms with integrations and secure workflows.",
        domain="legaltech",
    )


def test_orchestrator_happy_path(tmp_path):
    db = str(tmp_path / "runs.sqlite3")
    store = SQLiteStore(db)
    orch = Orchestrator(
        store=store,
        model_registry=ModelRegistry(manager=LLMManager(provider="deterministic")),
        agents=build_default_agents(),
    )

    response = orch.run(make_request())

    assert response.status in {"success", "degraded"}
    assert response.execution_plan is not None
    assert "market_agent" in response.agent_scores


def test_orchestrator_retry_then_degraded(tmp_path):
    db = str(tmp_path / "runs.sqlite3")
    store = SQLiteStore(db)
    defaults = build_default_agents()
    custom = AgentBundle(market=LowScoreMarketAgent(), competitor=defaults.competitor, browser=defaults.browser)
    orch = Orchestrator(
        store=store,
        model_registry=ModelRegistry(manager=LLMManager(provider="deterministic")),
        agents=custom,
    )

    response = orch.run(make_request())

    assert response.status == "degraded"
    assert response.agent_scores["market_agent"] < settings.min_agent_score
    assert any("market_agent" in risk for risk in response.unresolved_risks)
