from typing import Literal, Optional
from app.execution.contracts import ExecutionStatus, LLMPort, WorkerInput, WorkerOutput


class MockLLM:
    def __init__(self, behavior: Literal["complete", "error", "timeout"] = "complete"):
        if behavior not in {"complete", "error", "timeout"}:
            raise ValueError("Hành vi mock không hợp lệ.")
        self.behavior = behavior

    def generate(self, prompt: str) -> str:
        if self.behavior == "timeout":
            raise TimeoutError("Mock mô phỏng hết thời gian xử lý.")
        if self.behavior == "error":
            raise RuntimeError("Mock mô phỏng lỗi xử lý.")
        return prompt


class MockWorker:
    def __init__(self, llm: Optional[LLMPort] = None):
        self.llm = llm if llm is not None else MockLLM()

    def run(self, worker_input: WorkerInput) -> WorkerOutput:

        if not worker_input.evidence:
            return WorkerOutput(
                task_id=worker_input.task_id,
                status=ExecutionStatus.NO_EVIDENCE,
                answer="",
                evidence_ids=[],
                error=None,
            )

        prompt = "\n".join(item.text for item in worker_input.evidence)

        try:
            answer = self.llm.generate(prompt)
        except TimeoutError:
            return WorkerOutput(
                task_id=worker_input.task_id,
                status=ExecutionStatus.TIMEOUT,
                answer="",
                evidence_ids=[],
                error="Hết thời gian xử lý mock.",
            )
        except Exception:
            return WorkerOutput(
                task_id=worker_input.task_id,
                status=ExecutionStatus.FAILED,
                answer="",
                evidence_ids=[],
                error="Mock không thể xử lý tác vụ.",
            )

        evidence_ids = list(dict.fromkeys(item.evidence_id for item in worker_input.evidence))

        return WorkerOutput(
            task_id=worker_input.task_id,
            status=ExecutionStatus.COMPLETE,
            answer=answer,
            evidence_ids=evidence_ids,
            error=None,
        )