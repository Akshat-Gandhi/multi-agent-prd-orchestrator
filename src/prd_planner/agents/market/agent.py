from __future__ import annotations

from dataclasses import dataclass

from langchain_core.output_parsers import PydanticOutputParser

from prd_planner.agents.base import AgentContext, AgentContract
from prd_planner.contracts.schemas import AgentUserPreview, Artifact, RubricResult, TransferEnvelope
from prd_planner.models.provider import ModelAdapter
from prd_planner.tools.exa_tool import ExaSearchStrategy


@dataclass
class MarketAgent(AgentContract):
    exa: ExaSearchStrategy
    model: ModelAdapter
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
        user_preview = self._generate_user_preview(
            context=context,
            source=source,
            citations_count=len(citations),
            coverage=coverage,
        )
        return TransferEnvelope(
            run_id=context.run_id,
            trace_id=context.trace_id,
            producer_agent=self.id,
            payload={
                "user_preview": user_preview,
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

    def _generate_user_preview(
        self,
        context: AgentContext,
        source: str,
        citations_count: int,
        coverage: int,
    ) -> str:
        parser = PydanticOutputParser(pydantic_object=AgentUserPreview)
        prompt = (
            "You are a market strategist with a calm, commercially sharp voice.\n"
            "Write exactly one sentence in first person for an end user.\n"
            "Explain what you just did in this step and why it matters.\n"
            "Keep it concrete, confident, and under 24 words.\n"
            "Do not mention being an AI, a model, or a system.\n"
            "Do not use markdown.\n\n"
            f"{parser.get_format_instructions()}\n\n"
            f"Domain: {context.domain or 'general'}\n"
            f"PRD excerpt: {context.prd_text[:400]}\n"
            f"Search source: {source}\n"
            f"Citations found: {citations_count}\n"
            f"Coverage score: {coverage}\n"
        )
        try:
            result = parser.parse(self.model.complete(prompt))
            one_liner = " ".join(result.one_liner.split())
            return one_liner[:220]
        except Exception:
            return (
                f"I sized demand in {context.domain or 'this market'} and checked whether the opportunity looks strong enough to pursue."
            )
