"""Boundary between raw provider text and validated planning contracts."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .models import PlanningInput, PlanningIssue, RepairAction, RepairResult, TaskPlan

_JSON_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```", re.IGNORECASE | re.DOTALL)


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey("JSON objects must not contain duplicate keys")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError(f"Non-standard JSON constant: {value}")


def _input_issues(plan: TaskPlan, planning_input: PlanningInput) -> list[PlanningIssue]:
    issues: list[PlanningIssue] = []
    if plan.request_id != planning_input.request_id:
        issues.append(PlanningIssue(
            code="request_mismatch", path=("request_id",),
            message="Plan request_id must match PlanningInput.request_id.",
        ))
    if len(plan.tasks) > planning_input.max_tasks:
        issues.append(PlanningIssue(
            code="task_limit_exceeded", path=("tasks",),
            message="Plan exceeds PlanningInput.max_tasks.",
        ))
    roles = set(planning_input.available_roles)
    evidence = {item.id for item in planning_input.evidence}
    for index, task in enumerate(plan.tasks):
        if roles and task.role not in roles:
            issues.append(PlanningIssue(
                code="unknown_role", path=("tasks", index, "role"),
                message="Task role is not present in PlanningInput.available_roles.",
            ))
        if set(task.evidence_ids) - evidence:
            issues.append(PlanningIssue(
                code="unknown_evidence", path=("tasks", index, "evidence_ids"),
                message="Task refers to evidence not supplied in PlanningInput.",
            ))
    for name in ("obligations", "concerns"):
        supplied = getattr(planning_input, name)
        output = {item.id: item for item in getattr(plan, name)}
        for item in supplied:
            if output.get(item.id) != item:
                issues.append(PlanningIssue(
                    code="input_entity_changed", path=(name, item.id),
                    message=f"Previously supplied {name} must be preserved without changes.",
                ))
    return issues


def parse_planning_output(
    raw_output: str,
    planning_input: PlanningInput,
    *,
    max_output_chars: int = 1_000_000,
) -> RepairResult:
    """Parse one JSON object, check its graph, then validate it against the input.

    Only a leading UTF-8 BOM and one outer JSON Markdown fence can be repaired.
    No content, IDs, fields, dependencies, or JSON syntax are guessed or rewritten.
    A valid partial plan is returned with a warning; callers decide how to handle it.
    """
    if not isinstance(planning_input, PlanningInput):
        raise TypeError("planning_input must be a validated PlanningInput")
    planning_input = PlanningInput.model_validate(planning_input)
    if type(max_output_chars) is not int or max_output_chars < 1:
        raise ValueError("max_output_chars must be a positive integer")
    repairs: list[RepairAction] = []

    def failure(code: str, message: str) -> RepairResult:
        return RepairResult(
            status="invalid", issues=(PlanningIssue(code=code, message=message),),
            repairs=tuple(repairs),
        )

    if not isinstance(raw_output, str):
        return failure("invalid_format", "Provider output must be a string containing JSON.")
    if len(raw_output) > max_output_chars:
        return failure("output_too_large", "Provider output exceeds the character limit.")
    text = raw_output.strip()
    if text.startswith("\ufeff"):
        text = text[1:].strip()
        repairs.append("strip_bom")
    if text.startswith("```"):
        fence = _JSON_FENCE.fullmatch(text)
        if fence is None:
            return failure("invalid_format", "Expected exactly one outer JSON code fence.")
        text = fence.group(1).strip()
        repairs.append("unwrap_json_fence")
    try:
        payload = json.loads(
            text, object_pairs_hook=_unique_object, parse_constant=_reject_constant,
        )
    except _DuplicateKey as error:
        return failure("duplicate_key", str(error))
    except json.JSONDecodeError as error:
        return failure("invalid_json", f"Invalid JSON at line {error.lineno}, column {error.colno}.")
    except (ValueError, RecursionError):
        return failure("invalid_json", "Output is not a supported standards-compliant JSON value.")
    if not isinstance(payload, dict):
        return failure("invalid_format", "Planning output must be a JSON object.")
    try:
        plan = TaskPlan.model_validate(payload)
    except ValidationError as error:
        issues = tuple(
            PlanningIssue(code="schema_validation", path=item["loc"], message=item["msg"])
            for item in error.errors(include_input=False, include_context=False, include_url=False)
        )
        return RepairResult(status="invalid", issues=issues, repairs=tuple(repairs))
    issues = _input_issues(plan, planning_input)
    if issues:
        return RepairResult(status="invalid", issues=tuple(issues), repairs=tuple(repairs))
    if not plan.is_complete:
        issues.append(PlanningIssue(
            code="partial_plan", severity="warning",
            message="Plan explicitly declares obligations or concerns without an assigned task.",
        ))
    return RepairResult(
        status="repaired" if repairs else "valid", plan=plan,
        issues=tuple(issues), repairs=tuple(repairs),
    )
