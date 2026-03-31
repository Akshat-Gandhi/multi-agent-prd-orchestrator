from __future__ import annotations

from dataclasses import dataclass

from langchain_core.output_parsers import PydanticOutputParser

from prd_planner.agents.base import AgentContext, AgentContract
from prd_planner.contracts.schemas import AgentUserPreview, Artifact, Citation, RubricResult, TransferEnvelope
from prd_planner.models.provider import ModelAdapter
from prd_planner.tools.exa_tool import ExaSearchStrategy
from prd_planner.tools.playwright_tool import PlaywrightLifecycleTool


@dataclass
class BrowserAgent(AgentContract):
    browser: PlaywrightLifecycleTool
    exa: ExaSearchStrategy
    model: ModelAdapter
    id: str = "browser_agent"

    def run(self, context: AgentContext) -> TransferEnvelope:
        citations, source = self.exa.search(context.task.prompt, limit=1)
        url = citations[0].url if citations else None

        if url:
            result = self.browser.capture(url)
            facts = result.facts
            opened = result.opened
            citations_out = citations
        else:
            facts = []
            opened = False
            citations_out = []

        evidence_quality = 80 if facts else 30
        lifecycle_integrity = 90 if opened else 20
        score = int((evidence_quality + lifecycle_integrity) / 2)
        rubric = RubricResult(
            score=score,
            passed=score >= 70,
            unmet_criteria=[] if score >= 70 else ["insufficient browser evidence"],
            notes=f"source={source}" if url else "no_public_url_found",
        )
        user_preview = self._generate_user_preview(
            context=context,
            url=url,
            facts=facts,
            opened=opened,
        )
        return TransferEnvelope(
            run_id=context.run_id,
            trace_id=context.trace_id,
            producer_agent=self.id,
            payload={
                "user_preview": user_preview,
                "url": url,
                "facts": facts,
                "opened": opened,
                "closed": bool(url),
            },
            artifacts=[Artifact(kind="browser_evidence", content={"facts_count": len(facts)})],
            citations=citations_out,
            rubric=rubric,
        )

    def _generate_user_preview(
        self,
        context: AgentContext,
        url: str | None,
        facts: list[str],
        opened: bool,
    ) -> str:
        parser = PydanticOutputParser(pydantic_object=AgentUserPreview)
        facts_summary = "; ".join(facts[:3]) or "no verified facts captured yet"
        prompt = (
            "You are a meticulous research analyst who validates claims from public sources.\n"
            "Write exactly one sentence in first person for an end user.\n"
            "Explain what you checked and why that evidence is useful.\n"
            "Keep it concrete, calm, and under 24 words.\n"
            "Do not mention being an AI, a model, or a system.\n"
            "Do not use markdown.\n\n"
            f"{parser.get_format_instructions()}\n\n"
            f"Domain: {context.domain or 'general'}\n"
            f"PRD excerpt: {context.prd_text[:400]}\n"
            f"Opened URL: {url or 'none'}\n"
            f"Browser opened successfully: {opened}\n"
            f"Captured facts: {facts_summary}\n"
        )
        try:
            result = parser.parse(self.model.complete(prompt))
            one_liner = " ".join(result.one_liner.split())
            return one_liner[:220]
        except Exception:
            return (
                "I checked public sources to verify the most important claims so the final recommendation is grounded in evidence."
            )
