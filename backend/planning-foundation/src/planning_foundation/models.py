"""Validated contracts only: no retrieval, model calls, or task execution."""

from __future__ import annotations

from heapq import heappop, heappush
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    ),
]
Text = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=20_000),
]
LongText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100_000),
]


def _unique(values: tuple[str, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicate IDs")


def _known(values: tuple[str, ...], known: set[str], label: str) -> None:
    missing = sorted(set(values) - known)
    if missing:
        preview = ", ".join(missing[:8])
        suffix = f" (and {len(missing) - 8} more)" if len(missing) > 8 else ""
        raise ValueError(f"{label} refers to unknown IDs: {preview}{suffix}")


class ContractModel(BaseModel):
    """Immutable values; tuple collections remain immutable after validation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        revalidate_instances="always",
    )


class Obligation(ContractModel):
    """Yêu cầu bắt buộc: được giao cho task hoặc ghi rõ là chưa phân công."""

    id: Identifier
    description: Text
    source_excerpt: Text | None = Field(
        default=None, description="Optional quotation from the original request."
    )


class Concern(ContractModel):
    """Mối quan tâm cần xem xét, có thể liên quan đến nhiều yêu cầu."""

    id: Identifier
    description: Text
    obligation_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def unique_references(self) -> Self:
        _unique(self.obligation_ids, "Concern.obligation_ids")
        return self


class PlanningEvidence(ContractModel):
    """Evidence supplied by a retrieval adapter, not retrieved by this package."""

    id: Identifier
    document_id: Identifier
    content: LongText
    locator: Text | None = Field(default=None, description="Section, page, or other locator.")


class PlanningInput(ContractModel):
    """Câu hỏi gốc và dữ liệu đã biết từ các bước trước, nếu có."""

    schema_version: Literal["1.0"] = "1.0"
    request_id: Identifier
    request: LongText
    obligations: tuple[Obligation, ...] = Field(default=(), max_length=256)
    concerns: tuple[Concern, ...] = Field(default=(), max_length=256)
    evidence: tuple[PlanningEvidence, ...] = Field(default=(), max_length=256)
    available_roles: tuple[Identifier, ...] = Field(default=(), max_length=256)
    max_tasks: int = Field(default=16, strict=True, ge=1, le=256)

    @model_validator(mode="after")
    def consistent_input(self) -> Self:
        _unique(tuple(item.id for item in self.obligations), "PlanningInput.obligations")
        _unique(tuple(item.id for item in self.concerns), "PlanningInput.concerns")
        _unique(tuple(item.id for item in self.evidence), "PlanningInput.evidence")
        _unique(self.available_roles, "PlanningInput.available_roles")
        known = {item.id for item in self.obligations}
        for concern in self.concerns:
            _known(concern.obligation_ids, known, f"Concern {concern.id}")
        return self


class Task(ContractModel):
    """Một việc trong kế hoạch; module này chưa thực thi công việc đó."""

    id: Identifier
    title: Text
    description: Text
    role: Identifier = Field(description="Role identifier chosen by the surrounding system.")
    obligation_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=256)
    concern_ids: tuple[Identifier, ...] = Field(default=(), max_length=256)
    evidence_ids: tuple[Identifier, ...] = Field(default=(), max_length=256)

    @model_validator(mode="after")
    def unique_references(self) -> Self:
        for name in ("obligation_ids", "concern_ids", "evidence_ids"):
            _unique(getattr(self, name), f"Task.{name}")
        return self


class SemanticDependency(ContractModel):
    """A successor requires an output or derived context from its predecessor.

    These are directed execution prerequisites. Two tasks merely sharing the
    same document do not require a dependency edge.
    """

    predecessor_task_id: Identifier
    successor_task_id: Identifier
    kind: Literal["requires_output", "requires_context"] = "requires_output"
    rationale: Text

    @model_validator(mode="after")
    def distinct_tasks(self) -> Self:
        if self.predecessor_task_id == self.successor_task_id:
            raise ValueError("A task must not depend on itself")
        return self


def _topological_ids(
    task_ids: tuple[str, ...], dependencies: tuple[SemanticDependency, ...]
) -> tuple[str, ...]:
    """Stable order: prefer the declared task order among all ready tasks."""
    positions = {task_id: position for position, task_id in enumerate(task_ids)}
    children: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    indegree = {task_id: 0 for task_id in task_ids}
    for dependency in dependencies:
        children[dependency.predecessor_task_id].append(dependency.successor_task_id)
        indegree[dependency.successor_task_id] += 1
    ready: list[int] = []
    for task_id, degree in indegree.items():
        if degree == 0:
            heappush(ready, positions[task_id])
    ordered: list[str] = []
    while ready:
        task_id = task_ids[heappop(ready)]
        ordered.append(task_id)
        for successor in children[task_id]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heappush(ready, positions[successor])
    if len(ordered) != len(task_ids):
        raise ValueError("Task dependencies must form a directed acyclic graph")
    return tuple(ordered)


class TaskPlan(ContractModel):
    """Structured planning output with explicit coverage and one dependency graph."""

    schema_version: Literal["1.0"] = "1.0"
    request_id: Identifier
    obligations: tuple[Obligation, ...] = Field(min_length=1, max_length=256)
    concerns: tuple[Concern, ...] = Field(default=(), max_length=256)
    tasks: tuple[Task, ...] = Field(min_length=1, max_length=256)
    dependencies: tuple[SemanticDependency, ...] = Field(default=(), max_length=32_640)
    unassigned_obligation_ids: tuple[Identifier, ...] = Field(default=(), max_length=256)
    unassigned_concern_ids: tuple[Identifier, ...] = Field(default=(), max_length=256)

    @model_validator(mode="after")
    def consistent_plan(self) -> Self:
        # 1. Mỗi loại đối tượng phải có ID riêng, không trùng nhau.
        for name in ("obligations", "concerns", "tasks"):
            _unique(tuple(item.id for item in getattr(self, name)), f"TaskPlan.{name}")
        obligations = {item.id for item in self.obligations}
        concerns = {item.id for item in self.concerns}
        task_ids = tuple(item.id for item in self.tasks)
        for concern in self.concerns:
            _known(concern.obligation_ids, obligations, f"Concern {concern.id}")
        assigned_obligations: set[str] = set()
        assigned_concerns: set[str] = set()
        # 2. Task chỉ được tham chiếu yêu cầu và mối quan tâm có trong kế hoạch.
        for task in self.tasks:
            _known(task.obligation_ids, obligations, f"Task {task.id}.obligation_ids")
            _known(task.concern_ids, concerns, f"Task {task.id}.concern_ids")
            assigned_obligations.update(task.obligation_ids)
            assigned_concerns.update(task.concern_ids)
        # 3. Phần chưa phân công phải được khai báo, không được bỏ sót âm thầm.
        for name, all_ids, assigned in (
            ("unassigned_obligation_ids", obligations, assigned_obligations),
            ("unassigned_concern_ids", concerns, assigned_concerns),
        ):
            declared = getattr(self, name)
            _unique(declared, f"TaskPlan.{name}")
            _known(declared, all_ids, f"TaskPlan.{name}")
            if set(declared) != all_ids - assigned:
                raise ValueError(f"{name} must list exactly the IDs not assigned to any task")
        # 4. Quan hệ trước/sau phải tồn tại, không trùng và không tạo vòng lặp.
        known_tasks = set(task_ids)
        seen_edges: set[tuple[str, str]] = set()
        for dependency in self.dependencies:
            edge = (dependency.predecessor_task_id, dependency.successor_task_id)
            _known(edge, known_tasks, "SemanticDependency")
            if edge in seen_edges:
                raise ValueError("Duplicate dependency edge between the same two tasks")
            seen_edges.add(edge)
        _topological_ids(task_ids, self.dependencies)
        return self

    @property
    def is_complete(self) -> bool:
        """Structural assignment coverage, not proof of semantic correctness."""
        return not self.unassigned_obligation_ids and not self.unassigned_concern_ids

    def topological_task_ids(self) -> tuple[str, ...]:
        """An integration helper; this function does not execute tasks."""
        return _topological_ids(tuple(task.id for task in self.tasks), self.dependencies)


class PlanningIssue(ContractModel):
    code: Identifier
    message: Text
    path: tuple[str | int, ...] = ()
    severity: Literal["error", "warning"] = "error"


RepairAction = Literal["strip_bom", "unwrap_json_fence"]


class RepairResult(ContractModel):
    """Success/failure envelope, including any safe transport normalization."""

    status: Literal["valid", "repaired", "invalid"]
    plan: TaskPlan | None = None
    issues: tuple[PlanningIssue, ...] = ()
    repairs: tuple[RepairAction, ...] = ()

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        errors = any(issue.severity == "error" for issue in self.issues)
        if self.status == "invalid":
            if self.plan is not None or not errors:
                raise ValueError("An invalid result needs an error and must not contain a plan")
        elif self.plan is None or errors:
            raise ValueError("A successful result needs a plan and must not contain errors")
        if self.status == "valid" and self.repairs:
            raise ValueError("A valid result must not declare repairs")
        if self.status == "repaired" and not self.repairs:
            raise ValueError("A repaired result must declare at least one repair")
        if len(self.repairs) != len(set(self.repairs)):
            raise ValueError("Repair actions must not be duplicated")
        return self
