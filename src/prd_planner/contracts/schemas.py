from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, model_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Citation(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class Artifact(BaseModel):
    kind: str
    content: dict[str, Any]


class RubricResult(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    unmet_criteria: list[str] = Field(default_factory=list)
    notes: str | None = None


class AgentError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class TransferEnvelope(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    trace_id: str
    producer_agent: str
    payload: dict[str, Any]
    artifacts: list[Artifact] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    rubric: RubricResult
    errors: list[AgentError] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)


class RunRequest(BaseModel):
    prd_text: str = Field(min_length=20)
    domain: str | None = None
    constraints: list[str] = Field(default_factory=list)
    model_profile: str = "default"
    model_overrides: dict[str, str] = Field(default_factory=dict)


class Milestone(BaseModel):
    name: str = Field(description="Short milestone name that is easy for a stakeholder to scan.")
    description: str = Field(description="What will be delivered or achieved in this milestone.")
    owner: str = Field(description="Primary owner or role responsible for driving this milestone.")
    eta_days: int = Field(ge=1, description="Estimated number of days needed to complete this milestone.")


class ExecutionPlan(BaseModel):
    intent: str = Field(
        description="One sentence in plain language that explains the core purpose of the plan and what it is trying to achieve for the user."
    )
    explanation: str = Field(
        description="A short, first-person explanation for the end user describing why this plan makes sense given the PRD, constraints, and findings."
    )
    summary: str = Field(
        description="A concise overview of the recommended approach, written for a non-technical stakeholder."
    )
    milestones: list[Milestone] = Field(
        description="Ordered milestones that show how the work should progress from start to finish."
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Meaningful risks, tradeoffs, or uncertainties the user should know about before acting on the plan.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="External inputs, approvals, tools, integrations, or assumptions required for the plan to succeed.",
    )


class AgentUserPreview(BaseModel):
    one_liner: str = Field(
        description="A single first-person sentence for the end user that explains what this agent just did and why it matters."
    )


class RunResponse(BaseModel):
    run_id: str
    trace_id: str
    status: Literal["success", "degraded", "failed"]
    execution_plan: ExecutionPlan | None = None
    agent_scores: dict[str, int] = Field(default_factory=dict)
    unresolved_risks: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class RunLaunchResponse(BaseModel):
    run_id: str
    trace_id: str
    status: Literal["running"] = "running"


class RunStatusResponse(BaseModel):
    run_id: str
    trace_id: str
    status: Literal["running", "success", "degraded", "failed"]


class RunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    request: RunRequest
    status: Literal["running", "success", "degraded", "failed"] = "running"
    response: RunResponse | None = None


class EventRecord(BaseModel):
    run_id: str
    trace_id: str
    agent_id: str
    step: str
    event_type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now_iso)


class QualityGateResult(BaseModel):
    passed: bool
    overall_status: Literal["success", "degraded", "failed"]
    unresolved_risks: list[str] = Field(default_factory=list)


class AgentOutput(BaseModel):
    envelope: TransferEnvelope


class PlannerInput(BaseModel):
    run_id: str
    trace_id: str
    prd_text: str
    domain: str | None
    constraints: list[str]


class PlannerTask(BaseModel):
    title: str
    prompt: str
    desired_outputs: list[str] = Field(default_factory=list)


class PlannerTaskSet(BaseModel):
    market_task: PlannerTask
    competitor_task: PlannerTask
    browser_task: PlannerTask


class ValidationResult(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)


class ContractValidator:
    @staticmethod
    def validate_envelope(data: dict[str, Any]) -> ValidationResult:
        try:
            TransferEnvelope.model_validate(data)
            return ValidationResult(ok=True)
        except ValidationError as exc:
            return ValidationResult(ok=False, errors=[e["msg"] for e in exc.errors()])

    @staticmethod
    def validate_run_request(data: dict[str, Any]) -> ValidationResult:
        try:
            RunRequest.model_validate(data)
            return ValidationResult(ok=True)
        except ValidationError as exc:
            return ValidationResult(ok=False, errors=[e["msg"] for e in exc.errors()])


class OrchestratorState(BaseModel):
    run: RunRecord
    tasks: PlannerTaskSet | None = None
    market_output: TransferEnvelope | None = None
    competitor_output: TransferEnvelope | None = None
    browser_output: TransferEnvelope | None = None
    execution_plan: ExecutionPlan | None = None
    quality_gate: QualityGateResult | None = None
    retries: dict[str, int] = Field(default_factory=lambda: {"market": 0, "competitor": 0, "browser": 0})

    @model_validator(mode="after")
    def validate_retries(self) -> "OrchestratorState":
        for key in ("market", "competitor", "browser"):
            if key not in self.retries:
                self.retries[key] = 0
        return self
