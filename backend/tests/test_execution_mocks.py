import pytest

from app.execution import ExecutionStatus, MockLLM, MockWorker, WorkerInput
from app.retrieval.contracts import Evidence, Provenance


def worker_input():
    return WorkerInput(
        task_id="t1",
        instruction="Summarize supplied evidence",
        evidence=[
            Evidence(evidence_id="e1", text="A supplied fact.", provenance=Provenance(source_id="s1", chunk_id="c1")),
            Evidence(evidence_id="e2", text="Another supplied fact.", provenance=Provenance(source_id="s1", chunk_id="c2")),
        ],
    )


def test_mock_is_deterministic_and_uses_only_supplied_evidence():
    worker = MockWorker()
    request = worker_input()
    first = worker.run(request)
    assert first == worker.run(request)
    assert first.status == ExecutionStatus.COMPLETE
    assert first.answer == "A supplied fact.\nAnother supplied fact."
    assert first.evidence_ids == ["e1", "e2"]
    assert first.error is None


def test_empty_evidence_returns_no_evidence_without_model_call():
    request = worker_input().model_copy(update={"evidence": []})
    result = MockWorker(MockLLM("error")).run(request)
    assert result.status == ExecutionStatus.NO_EVIDENCE
    assert result.answer == ""
    assert result.evidence_ids == []


@pytest.mark.parametrize("behavior,status", [("error", ExecutionStatus.FAILED), ("timeout", ExecutionStatus.TIMEOUT)])
def test_simulated_failure_and_timeout(behavior, status):
    result = MockWorker(MockLLM(behavior)).run(worker_input())
    assert result.status == status
    assert result.error
    assert result.answer == ""
    assert result.evidence_ids == []


def test_mock_llm_echoes_text_without_inference():
    assert MockLLM().generate("supplied text") == "supplied text"
