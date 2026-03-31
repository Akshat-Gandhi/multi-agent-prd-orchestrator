from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from prd_planner.contracts.schemas import PlannerTask, PlannerTaskSet, TransferEnvelope


@dataclass
class AgentContext:
    run_id: str
    trace_id: str
    task: PlannerTask
    prd_text: str
    domain: str | None


class AgentContract(Protocol):
    id: str

    def run(self, context: AgentContext) -> TransferEnvelope:
        ...


class AgentPlugin(Protocol):
    def get_agent(self) -> AgentContract:
        ...
