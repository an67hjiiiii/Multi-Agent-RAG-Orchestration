# Planning Foundation — Sprint 1

Phần nền tảng lập kế hoạch của Kiều Đức Chung, task **CAPONE-32**.
Module nhận yêu cầu và một kế hoạch dạng JSON, kiểm tra dữ liệu rồi trả về
kế hoạch hợp lệ hoặc danh sách lỗi. JSON là cách lưu dữ liệu bằng các cặp tên–giá trị.

Hiện dùng kế hoạch mẫu để kiểm tra. Chưa gọi AI để tự phân tích câu hỏi,
chưa tìm tài liệu và chưa chạy các công việc trong kế hoạch.

## Chạy trong VS Code

Mở thư mục `planning-foundation`, chọn **Terminal → New Terminal**.
Cần Python 3.11 trở lên. Lần đầu chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Lệnh cài có thể cần mạng để tải Pydantic (thư viện kiểm tra dữ liệu).
Sau đó chạy demo và bộ kiểm thử:

```powershell
.\.venv\Scripts\python.exe examples/demo.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Không cần kích hoạt môi trường `.venv`. Nếu máy dùng lệnh `py` thay cho
`python`, đổi lệnh tạo môi trường thành `py -m venv .venv`.
Trong VS Code, chọn **Python: Select Interpreter** và trỏ tới Python trong `.venv`.
Chạy `examples/demo.py`; `models.py` chỉ khai báo dữ liệu nên chạy riêng sẽ không có demo.

Có thể chạy cả test và demo bằng `./scripts/check.ps1`.
Script ưu tiên `.venv`, hoặc nhận `-PythonBin 'C:\duong-dan\python.exe'`.

## Đọc code theo thứ tự nào?

```text
planning-foundation/
├── examples/
│   ├── planning_input.json    Câu hỏi và các yêu cầu đã biết
│   ├── task_plan.json         Kế hoạch mẫu được soạn sẵn
│   └── demo.py                Chạy bốn tình huống để trình bày
├── src/planning_foundation/
│   ├── models.py              Cấu trúc dữ liệu và các quy tắc kiểm tra
│   ├── parser.py              Đọc JSON, kiểm tra và trả kết quả
│   ├── schemas.py             Xuất mô tả cấu trúc JSON cho nhóm tích hợp
│   └── __init__.py            Các tên có thể import từ module
├── tests/                    Kiểm thử dữ liệu, parser và schema
├── schemas/                  Ba file mô tả JSON được xuất từ model
├── docs/
│   ├── luong-xu-ly.md         Giải thích luồng và gợi ý báo cáo
│   └── CAPONE-32.md           Đối chiếu Jira và Excel Sprint 1
├── scripts/check.ps1          Chạy test và demo trên Windows
├── pyproject.toml             Thông tin package và thư viện cần cài
└── README.md
```

Bắt đầu từ hai file JSON, chạy demo, đọc `parser.py`, rồi đọc từng model
trong `models.py`. Giữ `src/` để mã nguồn riêng với dữ liệu mẫu và kiểm thử;
không cần thêm các tầng service/repository/controller cho phần việc này.

## Luồng ngắn gọn

```text
Câu hỏi + dữ liệu đã biết → PlanningInput
Kế hoạch JSON            → parse_planning_output()
                           ├─ Bỏ lớp bọc định dạng nếu có
                           ├─ Kiểm tra cấu trúc và quan hệ trước/sau
                           ├─ Đối chiếu với PlanningInput
                           └─ RepairResult: kế hoạch hoặc lỗi
```

Demo minh họa: kế hoạch đúng, kế hoạch có lớp bọc Markdown, tham chiếu task
không tồn tại và kế hoạch còn thiếu phân công. Không có lời gọi AI ẩn trong demo.

| Tên trong code | Nghĩa và vai trò |
|---|---|
| `PlanningInput` | Dữ liệu đầu vào: câu hỏi, yêu cầu đã biết, tài liệu tham chiếu |
| `Obligation` | Yêu cầu bắt buộc phải đáp ứng |
| `Concern` | Mối quan tâm cần xem xét, ví dụ bảo mật |
| `Task` | Một công việc trong kế hoạch |
| `SemanticDependency` | Quan hệ công việc sau cần kết quả hoặc ngữ cảnh từ việc trước |
| `TaskPlan` | Toàn bộ kế hoạch và phần chưa phân công |
| `RepairResult` | Kết quả kiểm tra, lỗi và thay đổi định dạng đã thực hiện |

`valid` = đúng cấu trúc; `repaired` = đã bỏ lớp bọc định dạng;
`invalid` = không hợp lệ. Phải kiểm tra thêm `result.plan.is_complete`:
kế hoạch đúng cấu trúc vẫn có thể còn yêu cầu chưa được phân công.
Đủ phân công không chứng minh câu trả lời của AI đúng về nội dung.

## Tích hợp và bàn giao

Hàm chính là `parse_planning_output(raw_output, planning_input)`.
`raw_output` là chuỗi nội dung JSON, không phải toàn bộ phản hồi HTTP.
Ví dụ gọi hoàn chỉnh nằm trong `examples/demo.py`.

Khi sửa model, xuất lại schema (bản mô tả cấu trúc dữ liệu) rồi chạy test:

```powershell
.\.venv\Scripts\python.exe -m planning_foundation.schemas --output schemas
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- [Luồng xử lý và cách trình bày](docs/luong-xu-ly.md)
- [Đối chiếu Sprint 1 và điểm cần nhóm thống nhất](docs/CAPONE-32.md)

Đưa các file trong thư mục này lên GitHub. `.gitignore` loại `.venv`, bộ nhớ đệm,
file đóng gói và `.env` khỏi Git. Hai file JSON mẫu và ba schema cần được giữ lại.
