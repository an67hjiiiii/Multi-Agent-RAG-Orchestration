import pytest
from app.execution import ExecutionStatus, MockLLM, MockWorker, WorkerInput
from app.retrieval.contracts import Evidence, Provenance


def create_sample_input():
    return WorkerInput(
        task_id="t1",
        instruction="Tóm tắt tài liệu dẫn chứng",
        evidence=[
            Evidence(evidence_id="e1", text="Dữ liệu mẫu 1.", provenance=Provenance(source_id="s1", chunk_id="c1")),
            Evidence(evidence_id="e2", text="Dữ liệu mẫu 2.", provenance=Provenance(source_id="s1", chunk_id="c2")),
        ],
    )


def test_worker_run_success():
    worker = MockWorker()
    req = create_sample_input()
    result = worker.run(req)

    assert result.status == ExecutionStatus.COMPLETE
    assert result.answer == "Dữ liệu mẫu 1.\nDữ liệu mẫu 2."
    assert result.evidence_ids == ["e1", "e2"]
    assert result.error is None


def test_worker_empty_evidence():
    req = create_sample_input()
    req.evidence = []
    result = MockWorker(MockLLM("error")).run(req)

    assert result.status == ExecutionStatus.NO_EVIDENCE
    assert result.answer == ""
    assert result.evidence_ids == []


def test_worker_timeout():
    worker = MockWorker(MockLLM("timeout"))
    result = worker.run(create_sample_input())

    assert result.status == ExecutionStatus.TIMEOUT
    assert result.error == "Hết thời gian xử lý mock."
    assert result.answer == ""


def test_worker_error():
    worker = MockWorker(MockLLM("error"))
    result = worker.run(create_sample_input())

    assert result.status == ExecutionStatus.FAILED
    assert result.error == "Mock không thể xử lý tác vụ."
    assert result.answer == ""


def test_mock_llm_echo():
    llm = MockLLM()
    assert llm.generate("văn bản thử nghiệm") == "văn bản thử nghiệm"