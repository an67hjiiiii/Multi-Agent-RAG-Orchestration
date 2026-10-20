# Đối chiếu Sprint 1 — Kiều Đức Chung

Ngày rà soát: 07/10/2026. Nguồn: task Jira CAPONE-32 do nhóm cung cấp và
`Sprint1_Actual_CAP1.xlsx` ở thư mục ngoài mã nguồn. File Excel không được chỉnh sửa.

## Các việc trong Excel

Sáu dòng của Chung nằm tại `Estimate!C40:E45`, tương ứng `Actual!C39:E44`.

| Việc được giao | Phần có trong code | Kết luận trong phạm vi nền tảng |
|---|---|---|
| Tạo khung phân tích và lập kế hoạch yêu cầu | Package riêng, PlanningInput, parser, schema vào/ra | Đã có khung; chưa gọi AI |
| Xác định yêu cầu chính và các mối quan tâm | Obligation, Concern, liên kết và kiểm tra dữ liệu, ví dụ nhập sẵn | Có biểu diễn và kiểm tra; chưa tự trích xuất từ câu hỏi |
| Chuẩn hóa cấu trúc tác vụ và kế hoạch xử lý | Task, TaskPlan; kiểm tra trường, ID và phần chưa phân công | Đã có |
| Chuẩn hóa quan hệ phụ thuộc giữa các tác vụ | SemanticDependency; chặn tham chiếu sai, trùng cạnh, tự phụ thuộc, vòng lặp; tính thứ tự | Đã có |
| Xử lý kết quả AI sai định dạng | Đọc JSON; bỏ lớp bọc; trả lỗi có cấu trúc khi không hợp lệ | Đã có bằng dữ liệu mẫu; chưa kiểm tra phản hồi AI thực tế |
| Kiểm thử và hoàn thiện nền tảng Planning | Tests, demo và tài liệu cách chạy | Có kiểm thử độc lập; cần nhóm review tích hợp |

**Chưa nên ghi “hoàn tất toàn bộ sáu việc” theo nghĩa AI chạy thật.**
Jira giới hạn CAPONE-32 ở nền tảng và quy ước dữ liệu, chưa triển khai đầy đủ phân tích
bằng mô hình ngôn ngữ lớn (LLM). Nếu dòng thứ hai trong Excel yêu cầu tự đọc câu hỏi
để tách yêu cầu thì phần đó còn thiếu. Cần nhóm trưởng thống nhất cách nghiệm thu.

Các ô nhật ký thực tế `Actual!F39:S44` của Chung hiện đều trống; cần do người
thực hiện cập nhật đúng theo công việc.
Số ước tính của sáu dòng cộng lại là 19; tiêu đề chỉ ghi “Ước tính”, chưa xác nhận
đơn vị nên không coi đó là số giờ đã làm hay số việc đã hoàn thành.

Lưu ý công thức: `Actual!E39:E44` hiện chỉ cộng `F:O` (24/09–03/10),
trong khi lịch còn `P:S` (04/10–07/10). Nếu nhập số liệu bốn ngày cuối,
tổng hiện tại sẽ bỏ qua chúng. Cần người phụ trách Excel kiểm tra và mở rộng
phạm vi công thức theo quy ước của nhóm trước khi chốt báo cáo.

## Đối chiếu tiêu chí Jira CAPONE-32

| Tiêu chí | Bằng chứng |
|---|---|
| Module Planning riêng | `src/planning_foundation/`, các tên import trong `__init__.py` |
| Obligation, Concern | `models.py`, kiểm tra nội dung và liên kết |
| Task, TaskPlan | `models.py`, kiểm tra phân công và ID |
| SemanticDependency | `models.py`, kiểm tra quan hệ trước/sau |
| RepairResult | `models.py`, trạng thái và lỗi trả về |
| Schema đầu vào, đầu ra | PlanningInput, TaskPlan, RepairResult và ba file trong `schemas/` |
| Đọc kết quả có cấu trúc từ AI | `parse_planning_output()`, nhận chuỗi do bên gọi cung cấp |
| Xử lý sai định dạng, kiểm tra dữ liệu | `parser.py` và các quy tắc trong `models.py` |
| Kiểm thử các quy ước chính | Ba file `tests/test_*.py` |
| Chuẩn bị tích hợp Sprint sau | Hàm nhận/trả dữ liệu độc lập; cần thử với backend chung |

## Kết quả kiểm tra

Chạy lại ngày 07/10/2026: **44/44 kiểm thử đạt**, cả bốn tình huống demo đạt,
với Python 3.12.14 và Pydantic 2.13.5. Schema xuất lại khớp với model.
Môi trường chạy kiểm tra hạn chế ghi vào thư mục tạm hệ thống, nên lần xác minh
dùng thư mục tạm trong workspace; không thay đổi test để bỏ qua kiểm tra.
Bộ kiểm thử dùng `unittest` (thư viện kiểm thử có sẵn của Python).
Demo chạy không cần AI. Chưa thử trên mọi phiên bản Python/Pydantic được cho phép.
Các phép kiểm tra này xác nhận cấu trúc dữ liệu, không phải đánh giá chất lượng nghiên cứu.

## Nội dung cần nhóm review khi nhận code

1. Thống nhất tên trường và phiên bản schema `1.0` trước khi nối các module.
2. Thống nhất việc tách yêu cầu/mối quan tâm ở Sprint này hay Sprint sau.
3. `Task.role` hiện bắt buộc có vai trò. Trong sơ đồ nhóm, phân vai nằm ở bước
   DAG/Routing (xếp quan hệ và điều phối). Cần chốt vai trò đề xuất ở Planning
   hay bổ sung một cấu trúc trung gian trước Routing; chưa tự đổi contract.
4. Quan hệ phụ thuộc chỉ lưu tại `TaskPlan.dependencies`, tránh thêm bản sao
   `Task.depends_on` rồi cập nhật lệch nhau.
5. Thống nhất cách xử lý kế hoạch còn thiếu và số lần yêu cầu AI làm lại.
6. Kiểm tra với phần Execution (thực thi) của Bảo; phần kiểm tra Planning/Execution
   trong Excel được giao Mai tại `Estimate!C55:D55`.

Bản này sẵn sàng để review phần nền tảng. Chưa có bằng chứng chạy tích hợp toàn hệ thống,
chưa có kết quả đánh giá với mô hình AI và chưa thay đổi trạng thái Jira.
