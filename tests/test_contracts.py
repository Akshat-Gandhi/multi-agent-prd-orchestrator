from prd_planner.contracts.schemas import ContractValidator, RubricResult, TransferEnvelope


def test_transfer_envelope_validation_ok():
    envelope = TransferEnvelope(
        run_id="r1",
        trace_id="t1",
        producer_agent="market_agent",
        payload={"x": 1},
        rubric=RubricResult(score=80, passed=True),
    )
    result = ContractValidator.validate_envelope(envelope.model_dump())
    assert result.ok is True


def test_transfer_envelope_validation_fails_for_missing_fields():
    result = ContractValidator.validate_envelope({"run_id": "r1"})
    assert result.ok is False
    assert result.errors
