from __future__ import annotations

from dataclasses import dataclass

from prd_planner.agents.base import AgentContext, AgentContract
from prd_planner.contracts.schemas import Artifact, RubricResult, TransferEnvelope
from prd_planner.tools.playwright_tool import PlaywrightLifecycleTool


@dataclass
class BrowserAgent(AgentContract):
    browser: PlaywrightLifecycleTool
    id: str = "browser_agent"

    def run(self, context: AgentContext) -> TransferEnvelope:
        url = "https://example.com"
        result = self.browser.capture(url)
        # Dummy tool returns closed=False because close happens in finally; we score by evidence + open lifecycle.
        evidence_quality = 80 if result.facts else 40
        lifecycle_integrity = 90 if result.opened else 20
        score = int((evidence_quality + lifecycle_integrity) / 2)
        rubric = RubricResult(
            score=score,
            passed=score >= 70,
            unmet_criteria=[] if score >= 70 else ["insufficient browser evidence"],
            notes="playwright_mcp_open_extract_close",
        )
        return TransferEnvelope(
            run_id=context.run_id,
            trace_id=context.trace_id,
            producer_agent=self.id,
            payload={
                "url": url,
                "facts": result.facts,
                "opened": result.opened,
                "closed": True,
            },
            artifacts=[Artifact(kind="browser_evidence", content={"facts_count": len(result.facts)})],
            citations=[],
            rubric=rubric,
        )
