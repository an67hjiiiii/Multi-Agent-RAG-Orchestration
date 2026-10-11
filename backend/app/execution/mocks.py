"""Deterministic test doubles; their output is not live semantic evidence."""

from typing import Literal

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
    def __init__(self, llm: LLMPort | None = None):
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

        # Echo only supplied evidence so this test double cannot invent context.
        prompt = "\n".join(item.text for item in worker_input.evidence)
        try:
            answer = self.llm.generate(prompt)
        except TimeoutError:
            return self._failure(worker_input, ExecutionStatus.TIMEOUT, "Hết thời gian xử lý mock.")
        except Exception:
            return self._failure(worker_input, ExecutionStatus.FAILED, "Mock không thể xử lý tác vụ.")
        return WorkerOutput(
            task_id=worker_input.task_id,
            status=ExecutionStatus.COMPLETE,
            answer=answer,
            evidence_ids=list(dict.fromkeys(item.evidence_id for item in worker_input.evidence)),
            error=None,
        )

    @staticmethod
    def _failure(worker_input: WorkerInput, status: ExecutionStatus, error: str) -> WorkerOutput:
        return WorkerOutput(
            task_id=worker_input.task_id,
            status=status,
            answer="",
            evidence_ids=[],
            error=error,
        )
