from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_core.output_parsers import PydanticOutputParser

from prd_planner.agents.base import AgentContext, AgentContract
from prd_planner.contracts.schemas import (
    AgentUserPreview,
    Artifact,
    Citation,
    RubricResult,
    TransferEnvelope,
)
from prd_planner.models.provider import ModelAdapter
from prd_planner.tools.exa_tool import ExaSearchStrategy


@dataclass
class CompetitorAgent(AgentContract):
    exa: ExaSearchStrategy
    model: ModelAdapter
    id: str = "competitor_agent"

    def run(self, context: AgentContext) -> TransferEnvelope:
        citations, source = self.exa.search(context.task.prompt)
        competitors = self._extract_competitors(citations)
        comparison_confidence = 75 if citations else 40
        score = int((80 + 75 + comparison_confidence) / 3)
        rubric = RubricResult(
            score=score,
            passed=score >= 70,
            unmet_criteria=(
                [] if score >= 70 else ["low confidence in competitor comparison"]
            ),
            notes=f"source={source}",
        )
        user_preview = self._generate_user_preview(
            context=context,
            competitors=competitors,
            source=source,
            citations_count=len(citations),
        )
        return TransferEnvelope(
            run_id=context.run_id,
            trace_id=context.trace_id,
            producer_agent=self.id,
            payload={
                "user_preview": user_preview,
                "competitors": competitors,
                "comparison_confidence": comparison_confidence,
                "source": source,
            },
            artifacts=[
                Artifact(
                    kind="competitor_analysis", content={"count": len(competitors)}
                )
            ],
            citations=citations,
            rubric=rubric,
        )

    def _generate_user_preview(
        self,
        context: AgentContext,
        competitors: list[dict[str, str]],
        source: str,
        citations_count: int,
    ) -> str:
        parser = PydanticOutputParser(pydantic_object=AgentUserPreview)
        competitor_names = ", ".join(item["name"] for item in competitors[:4]) or "no clear named competitors yet"
        prompt = (
            "You are a competitive intelligence analyst with a sharp, strategic voice.\n"
            "Write exactly one sentence in first person for an end user.\n"
            "Explain what you just compared and why that comparison is useful.\n"
            "Keep it concrete, confident, and under 24 words.\n"
            "Do not mention being an AI, a model, or a system.\n"
            "Do not use markdown.\n\n"
            f"{parser.get_format_instructions()}\n\n"
            f"Domain: {context.domain or 'general'}\n"
            f"PRD excerpt: {context.prd_text[:400]}\n"
            f"Competitors identified: {competitor_names}\n"
            f"Search source: {source}\n"
            f"Citations found: {citations_count}\n"
        )
        try:
            result = parser.parse(self.model.complete(prompt))
            one_liner = " ".join(result.one_liner.split())
            return one_liner[:220]
        except Exception:
            return (
                f"I mapped the strongest alternatives in {context.domain or 'this category'} so you can see where this product needs to stand out."
            )

    def _extract_competitors(self, citations: list[Citation]) -> list[dict[str, str]]:
        competitors: list[dict[str, str]] = []
        seen: set[str] = set()

        for citation in citations:
            title = citation.title.strip()
            if not title:
                continue
            candidate = re.split(r"[:|\-]| vs\.? ", title, maxsplit=1)[0].strip()
            candidate = re.sub(r"\s+", " ", candidate)
            if len(candidate) < 3:
                continue
            normalized = candidate.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            competitors.append(
                {
                    "name": candidate,
                    "positioning": "Derived from cited source",
                    "pricing": "Not yet confirmed",
                }
            )
            if len(competitors) >= 5:
                break

        return competitors
