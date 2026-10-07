"""Demo bằng dữ liệu mẫu, không gọi AI và không cần kết nối mạng."""

import json
import sys
from pathlib import Path

from planning_foundation import PlanningInput, TaskPlan, parse_planning_output


def main() -> None:
    # Giữ tiếng Việt đọc được trong terminal Windows và khi chuyển hướng output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    directory = Path(__file__).resolve().parent
    planning_input = PlanningInput.model_validate_json(
        (directory / "planning_input.json").read_text(encoding="utf-8")
    )
    output = (directory / "task_plan.json").read_text(encoding="utf-8")
    print("DEMO PLANNING FOUNDATION — dữ liệu soạn sẵn, chưa gọi AI\n")
    print(f"Yêu cầu: {planning_input.request}")
    print("\n1. Kế hoạch đúng cấu trúc")
    result = parse_planning_output(output, planning_input)
    assert result.plan is not None
    assert result.status == "valid"
    print(f"Trạng thái: {result.status} (hợp lệ)")
    for task in result.plan.tasks:
        print(f"  {task.id}: {task.title}; vai trò: {task.role}")
    print(f"Đã phân công hết yêu cầu đã khai báo: {result.plan.is_complete}")
    print(f"Thứ tự theo phụ thuộc: {' -> '.join(result.plan.topological_task_ids())}")
    print("  Thiết kế dữ liệu trước, sau đó thiết kế API dựa trên dữ liệu đó.")
    assert TaskPlan.model_validate_json(result.plan.model_dump_json()) == result.plan

    print("\n2. Kế hoạch bị bọc trong khối mã Markdown")
    repaired = parse_planning_output(f"```json\n{output}\n```", planning_input)
    assert repaired.status == "repaired"
    print(f"Trạng thái: {repaired.status} (đã bỏ lớp bọc, không sửa nội dung kế hoạch)")

    print("\n3. Kế hoạch tham chiếu một task không tồn tại")
    broken = json.loads(output)
    broken["dependencies"][0]["predecessor_task_id"] = "T-missing"
    rejected = parse_planning_output(json.dumps(broken), planning_input)
    assert rejected.status == "invalid" and rejected.plan is None
    print(f"Trạng thái: {rejected.status} (bị từ chối vì T-missing không tồn tại)")
    print(f"Chi tiết lỗi từ bộ kiểm tra: {rejected.issues[0].message}")

    print("\n4. Kế hoạch còn yêu cầu chưa phân công")
    partial = json.loads(output)
    partial["tasks"] = [partial["tasks"][0]]
    partial["dependencies"] = []
    partial["unassigned_obligation_ids"] = ["O-data"]
    incomplete = parse_planning_output(json.dumps(partial), planning_input)
    assert incomplete.plan is not None and not incomplete.plan.is_complete
    print(f"Trạng thái: {incomplete.status} (đúng cấu trúc nhưng chưa phân công đủ)")
    print("Cảnh báo: O-data chưa có task xử lý; bước điều phối cần xử lý tiếp.")
    print("\nHoàn tất 4 tình huống. Demo chỉ kiểm tra kế hoạch, chưa thực thi các task.")


if __name__ == "__main__":
    main()
