from __future__ import annotations

from dataclasses import dataclass

from prd_planner.agents.base import AgentContext, AgentContract
from prd_planner.contracts.schemas import Artifact, Citation, RubricResult, TransferEnvelope
from prd_planner.tools.exa_tool import ExaSearchStrategy


@dataclass
class CompetitorAgent(AgentContract):
    exa: ExaSearchStrategy
    id: str = "competitor_agent"

    def run(self, context: AgentContext) -> TransferEnvelope:
        citations, source = self.exa.search(context.task.prompt)
        competitors = [
            {"name": "Competitor A", "positioning": "SMB-first", "pricing": "Tiered"},
            {"name": "Competitor B", "positioning": "Enterprise", "pricing": "Seat-based"},
        ]
        comparison_confidence = 75 if citations else 40
        score = int((80 + 75 + comparison_confidence) / 3)
        rubric = RubricResult(
            score=score,
            passed=score >= 70,
            unmet_criteria=[] if score >= 70 else ["low confidence in competitor comparison"],
            notes=f"source={source}",
        )
        return TransferEnvelope(
            run_id=context.run_id,
            trace_id=context.trace_id,
            producer_agent=self.id,
            payload={
                "competitors": competitors,
                "comparison_confidence": comparison_confidence,
                "source": source,
            },
            artifacts=[Artifact(kind="competitor_analysis", content={"count": len(competitors)})],
            citations=citations
            + [Citation(title="Competitor matrix", url="https://example.com/matrix", snippet="Feature comparisons")],
            rubric=rubric,
        )
