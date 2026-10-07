# Luồng xử lý và cách trình bày

## Ví dụ đang chạy

Người dùng yêu cầu thiết kế API tạo project và cấu trúc cơ sở dữ liệu.
Mọi thao tác phải kiểm tra `tenant_id` (mã tổ chức/nhóm sở hữu dữ liệu)
để tránh đọc hoặc sửa dữ liệu của nhóm khác.

Trong `planning_input.json`, yêu cầu đã được người viết ví dụ tách sẵn thành:

- `O-api`: thiết kế API, tức giao diện để các chương trình trao đổi dữ liệu.
- `O-data`: thiết kế cấu trúc cơ sở dữ liệu.
- `O-security`: kiểm tra quyền truy cập theo tổ chức sở hữu.
- `C-security`: mối quan tâm bảo mật xuyên suốt.

`Obligation` là điều bắt buộc phải làm; `Concern` là góc cần quan tâm.
Một yêu cầu bảo mật bắt buộc vẫn phải có trong Obligation, không chỉ ghi Concern.

Kế hoạch mẫu có hai việc: `T-data` thiết kế dữ liệu và `T-api` thiết kế API.
Cả hai cùng phải xử lý yêu cầu bảo mật. `T-api` cần kết quả của `T-data`,
nên thứ tự hợp lệ là `T-data → T-api` dù thứ tự lưu trong JSON ngược lại.

## Lần theo một lượt chạy

1. `examples/demo.py` đọc hai file mẫu. `PlanningInput.model_validate_json()`
   chuyển JSON đầu vào thành đối tượng Python và kiểm tra các trường.
2. Demo đưa chuỗi kế hoạch vào `parse_planning_output()` trong `parser.py`.
3. Parser (bộ đọc dữ liệu) bỏ BOM đầu chuỗi nếu có và một lớp bọc mã Markdown.
   BOM là ký tự đánh dấu mã hóa; lớp bọc Markdown là ba dấu backtick quanh JSON.
4. `json.loads()` đọc chuỗi thành dữ liệu. Sai cú pháp hoặc trùng tên trường
   sẽ trả lỗi, không đoán nội dung để sửa.
5. `TaskPlan.model_validate()` gọi các quy tắc trong `models.py`: ID không trùng,
   tham chiếu phải tồn tại, yêu cầu chưa phân công phải được ghi rõ,
   quan hệ phụ thuộc không được tạo vòng lặp.
6. `_input_issues()` đối chiếu mã yêu cầu, giới hạn số việc, vai trò, tài liệu
   tham chiếu và các yêu cầu đã biết ở đầu vào.
7. Trả `RepairResult`. Nếu không hợp lệ thì `plan=None` và có danh sách `issues`
   (các lỗi). Nếu hợp lệ thì có kế hoạch; vẫn cần kiểm tra phần chưa phân công.

`topological_task_ids()` sắp xếp trước/sau theo quan hệ phụ thuộc.
DAG là đồ thị có hướng không có chu trình: A cần B thì không được đồng thời
bắt B chờ A. Hàm này chỉ tính thứ tự, chưa chạy các công việc.

## Khi báo cáo, mở gì và nói gì?

Mở hai file JSON rồi chạy `examples/demo.py` theo README. Demo có bốn tình huống:

| Tình huống | Kết quả cần giải thích |
|---|---|
| Kế hoạch đúng | Nhận kế hoạch, trả thứ tự T-data rồi T-api |
| Có lớp bọc Markdown | Bỏ lớp bọc, giữ nguyên nội dung |
| Phụ thuộc T-missing | Từ chối vì công việc đó không tồn tại |
| Chưa phân công O-data | Đúng cấu trúc nhưng chưa đầy đủ, có cảnh báo |

Sau đó chạy bộ kiểm thử để minh họa các trường hợp còn lại như phụ thuộc vòng,
ID trùng, sai vai trò và tài liệu tham chiếu không tồn tại.

Có thể trình bày bằng lời của mình:

> Em phụ trách nền tảng của phần lập kế hoạch. Em xây dựng cách biểu diễn yêu cầu,
> mối quan tâm, công việc và quan hệ trước/sau, cùng bộ kiểm tra kế hoạch.
> Demo này dùng dữ liệu soạn sẵn để kiểm tra việc nhận kế hoạch đúng và từ chối
> kế hoạch lỗi. Phần tự dùng AI để tách câu hỏi, lập kế hoạch và thực thi công việc
> chưa nằm trong bản demo này. Bước tiếp theo là thống nhất dữ liệu với nhóm
> và nối phần lập kế hoạch vào luồng xử lý chung.

Chỉ báo cáo tiến độ cá nhân từ code đã kiểm tra; tiến độ cả nhóm cần nhóm trưởng tổng hợp.

## Các quy tắc cần giữ khi tích hợp

- Contract là quy ước dữ liệu giữa các module; schema là bản mô tả các trường.
  Schema JSON không thay thế kiểm tra quan hệ giữa các ID trong Python.
- Model không cho sửa trực tiếp sau khi tạo. Muốn thay đổi kế hoạch, tạo dữ liệu
  mới rồi kiểm tra lại; tránh bỏ qua kiểm tra bằng `model_construct()` hoặc
  `model_copy(update=...)`.
- Mỗi task phải gắn với ít nhất một yêu cầu. Có thể chia sẻ yêu cầu và tài liệu;
  cùng dùng một tài liệu không có nghĩa là hai task phải chờ nhau.
- Hai loại phụ thuộc: `requires_output` cần kết quả, `requires_context` cần
  ngữ cảnh do task trước tạo ra. Cả hai đều là điều kiện phải chờ.
- `available_roles` rỗng nghĩa là chưa giới hạn vai trò. `evidence` rỗng nghĩa
  là không có mã tài liệu nào được phép tham chiếu.
- Đầu vào có thể chỉ có câu hỏi. Parser không tự đọc hiểu câu hỏi để tách yêu cầu;
  phần lập kế hoạch sau này phải sinh chúng trong đầu ra.
- Yêu cầu và mối quan tâm đã có ở đầu vào phải được giữ nguyên trong kế hoạch.
- `is_complete` chỉ cho biết các yêu cầu đã khai báo đều có task phụ trách.
  Nó không kiểm tra được yêu cầu bị bỏ sót ngay từ bước đọc hiểu câu hỏi.
- Kế hoạch còn thiếu phân công cần được điều phối xử lý tiếp, không coi là hoàn tất.
- Bộ đọc giới hạn đầu ra một triệu ký tự. Chỉ sửa lớp bọc định dạng;
  không tự sửa ý nghĩa, bịa task hay thay đổi quan hệ phụ thuộc.
