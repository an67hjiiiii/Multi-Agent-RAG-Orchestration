from enum import Enum
from typing import Protocol, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.contracts import Evidence


class ExecutionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_EVIDENCE = "NO_EVIDENCE"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class LLMPort(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class WorkerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)


class WorkerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    status: ExecutionStatus
    answer: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    event: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ExecutionStatus
    outputs: list[WorkerOutput] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)