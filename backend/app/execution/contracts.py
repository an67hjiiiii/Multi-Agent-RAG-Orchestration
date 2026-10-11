"""Synchronous execution contracts without scheduling or model integration."""

from enum import Enum
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.retrieval.contracts import Evidence


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_EVIDENCE = "NO_EVIDENCE"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class LLMPort(Protocol):
    def generate(self, prompt: str) -> str:
        """Return text or raise an execution error synchronously."""
        ...


class WorkerInput(ExecutionModel):
    task_id: NonBlank
    instruction: NonBlank
    evidence: list[Evidence]


class WorkerOutput(ExecutionModel):
    task_id: NonBlank
    status: ExecutionStatus
    answer: str
    evidence_ids: list[NonBlank]
    error: NonBlank | None


class TraceEvent(ExecutionModel):
    task_id: NonBlank
    event: NonBlank
    message: NonBlank


class ExecutionResult(ExecutionModel):
    status: ExecutionStatus
    outputs: list[WorkerOutput]
    trace: list[TraceEvent]
