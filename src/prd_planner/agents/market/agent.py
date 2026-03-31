from __future__ import annotations

from dataclasses import dataclass

from prd_planner.agents.base import AgentContext, AgentContract
from prd_planner.contracts.schemas import Artifact, RubricResult, TransferEnvelope
from prd_planner.tools.exa_tool import ExaSearchStrategy


@dataclass
class MarketAgent(AgentContract):
    exa: ExaSearchStrategy
    id: str = "market_agent"

    def run(self, context: AgentContext) -> TransferEnvelope:
        citations, source = self.exa.search(context.task.prompt)
        coverage = min(100, 50 + len(citations) * 15)
        relevance = 80 if context.domain else 70
        citation_quality = 80 if citations else 20
        score = int((coverage + relevance + citation_quality) / 3)
        rubric = RubricResult(
            score=score,
            passed=score >= 70,
            unmet_criteria=[] if score >= 70 else ["insufficient market evidence"],
            notes=f"source={source}",
        )
        return TransferEnvelope(
            run_id=context.run_id,
            trace_id=context.trace_id,
            producer_agent=self.id,
            payload={
                "market_summary": f"Market trends analyzed for domain={context.domain or 'general'}",
                "coverage": coverage,
                "relevance": relevance,
                "citation_quality": citation_quality,
                "source": source,
            },
            artifacts=[Artifact(kind="market_analysis", content={"query": context.task.prompt})],
            citations=citations,
            rubric=rubric,
        )
