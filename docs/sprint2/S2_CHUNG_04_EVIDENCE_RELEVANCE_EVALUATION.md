# CAPONE-65: Đánh giá mức độ phù hợp evidence và tổng hợp gap theo kịch bản

- Người phụ trách: Kiều Đức Chung.
- Technical Task: `S2-CHUNG-04`.
- Jira: [CAPONE-65](https://thanhhai2kar5.atlassian.net/browse/CAPONE-65).
- Ngày lập: 18/10/2026.
- Phạm vi: `DOC_ONLY` — Phân tích chất lượng trích xuất bằng chứng (relevance) và xác định các khoảng trống (gaps) dữ liệu cho chức năng Simple Ask.

---

## 1. Mục đích đánh giá

Tài liệu này thực hiện đánh giá mức độ phù hợp (relevance) của evidence đối với 12 kịch bản Simple Ask (đã được chuẩn hóa tại [CAPONE-64](https://thanhhai2kar5.atlassian.net/browse/CAPONE-64)), nhằm:
1. Xác định mức độ đáp ứng của kho tài liệu tri thức hiện tại đối với từng câu hỏi tra cứu.
2. Ghi nhận các trường hợp bằng chứng yếu hoặc thiếu thông tin (gaps).
3. Đưa ra các kết luận kỹ thuật làm cơ sở để cải thiện pipeline Retrieval và cơ chế trả lời grounded response trong Sprint 2 và Sprint tiếp theo.

---

## 2. Bảng tổng hợp Relevance & Gap cho 12 tình huống

Dưới đây là kết quả đối chiếu và đánh giá chi tiết theo từng tình huống:

| Mã case | Miền kỹ thuật | Câu hỏi tra cứu | Mức độ phù hợp | Đánh giá bằng chứng trong tài liệu | Khoảng trống dữ liệu & Lưu ý (Gap) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `M0-01` | Security | Authentication verifies what in this system? | `DIRECT` | `demo_security.md` nêu trực tiếp: xác thực dùng để kiểm tra và xác minh danh tính người dùng. | Không có gap lớn. Bằng chứng trực tiếp, rõ ràng. |
| `M0-02` | Security | What does authorization check before an action is allowed? | `DIRECT` | `demo_security.md` nêu rõ: phân quyền kiểm tra vai trò và quyền hạn của người dùng đã xác thực trước khi cho phép thực thi. | Bằng chứng đầy đủ cho câu hỏi đơn lẻ. |
| `M0-03` | Security | Can JWT claims replace server-side authorization policy? | `SUPPORTING` | `demo_security.md` nêu ràng buộc phía server phải kiểm tra lại chính sách thay vì chỉ tin tưởng claims của JWT. | **Gap:** Tài liệu chưa chi tiết hóa cơ chế thu hồi token (token revocation) hoặc vòng đời refresh token. |
| `M0-04` | Database | Where are user records stored? | `DIRECT` | `demo_database.md` nêu rõ: bản ghi người dùng được lưu trữ trong cơ sở dữ liệu quan hệ (PostgreSQL). | Đạt yêu cầu tra cứu vị trí lưu trữ. |
| `M0-05` | Database | Which database queries should be reviewed for indexes? | `DIRECT` | `demo_database.md` nêu tiêu chí: các truy vấn lọc thường xuyên theo định danh và trường điều kiện cần đánh chỉ mục. | Bằng chứng đủ định hướng kỹ thuật. |
| `M0-06` | Database | When are transaction boundaries required? | `DIRECT` | `demo_database.md` xác định: ranh giới transaction bắt buộc cho các thao tác ghi nhiều bước để đảm bảo tính nhất quán dữ liệu. | Đạt yêu cầu. |
| `M0-07` | API | What kind of endpoints does the service expose? | `DIRECT` | `demo_api.md` nêu cụ thể: dịch vụ cung cấp các REST endpoints chuẩn. | Bằng chứng trực tiếp. |
| `M0-08` | API | What should API contracts define? | `SUPPORTING` | `demo_api.md` nêu các yêu cầu về kiểm tra dữ liệu đầu vào và cấu trúc phản hồi lỗi. | **Gap:** Chưa có quy định cụ thể về chuẩn đặc tả schema (như OpenAPI 3.0 hay JSON Schema). |
| `M0-09` | Architecture | When should architectural dependencies be explicit? | `DIRECT` | `demo_api.md` quy định: các phụ thuộc giữa các module/tác vụ phải được khai báo tường minh khi đầu ra tác vụ này là đầu vào tác vụ khác. | Đạt yêu cầu về nguyên tắc kiến trúc. |
| `M0-10` | Đối chứng thiếu | What is the production deployment region? | `MISSING` | Cả 3 tài liệu không có thông tin về vùng triển khai (region/datacenter). | **Gap dữ liệu:** Kho tri thức chưa nạp thông tin hạ tầng. Hệ thống bắt buộc trả về `NO_EVIDENCE` và citation rỗng để tránh suy diễn. |
| `M0-11` | Đối chứng thiếu | What is the user's password minimum length? | `MISSING` | Tài liệu Security không nêu quy định cụ thể về độ dài mật khẩu tối thiểu. | **Gap dữ liệu:** Thiếu chính sách mật khẩu chi tiết. Cần xử lý trả về `NO_EVIDENCE`. |
| `M0-12` | Đối chứng thiếu | What is the monthly SLA percentage? | `MISSING` | Cả 3 tài liệu không chứa cam kết phần trăm SLA dịch vụ. | **Gap dữ liệu:** Thiếu cam kết mức độ dịch vụ. Cần xử lý trả về `NO_EVIDENCE`. |

---

## 3. Các khoảng trống kỹ thuật tồn tại (Technical Gaps)

Từ kết quả đánh giá 12 kịch bản trên, ghi nhận các khoảng trống kỹ thuật cần lưu ý:

1. **Giới hạn phạm vi của kho tài liệu thử nghiệm (Corpus Limitations):**
   * Tập dữ liệu tài liệu hiện tại tập trung vào 3 file demo nhỏ (`demo_security.md`, `demo_database.md`, `demo_api.md`). Các thông tin vận hành, hạ tầng, triển khai chưa được nạp vào hệ thống, dẫn đến các case `M0-10`, `M0-11`, `M0-12` thiếu bằng chứng.
   * Đây là các kịch bản đối chứng âm cần thiết để đảm bảo tính trung thực (faithfulness), ngăn chặn hiện tượng model tự bịa trích dẫn khi tài liệu không có thật.

2. **Ranh giới giữa so khớp từ khóa và hiểu ngữ nghĩa:**
   * Các kịch bản có bằng chứng hiện tại chủ yếu kiểm tra khả năng tìm kiếm theo từ khóa trực tiếp (lexical match).
   * Chưa đo lường đầy đủ độ chính xác khi câu hỏi sử dụng từ đồng nghĩa, câu hỏi đa bước (multi-hop) cần kết hợp thông tin từ nhiều file, hoặc các trường hợp câu hỏi có tính chất phủ định (negation).

3. **Chưa thực hiện đánh giá ngữ nghĩa trên mô hình thực tế:**
   * Tài liệu này tập trung đánh giá tĩnh trên nội dung tài liệu và kịch bản đầu vào.
   * Các trường đánh giá tính đúng đắn (`correctness`) và độ trung thực (`faithfulness`) của câu trả lời do Local LLM (Ollama) sinh ra trên máy thật cần được kiểm nghiệm trong các bài test runtime tiếp theo.

---

## 4. Kết luận và Kiến nghị

* **Kết luận:** Bộ tài liệu và 12 kịch bản đã xây dựng đáp ứng tốt mục tiêu phân loại và kiểm tra chức năng Simple Ask của Sprint 2. Bằng chứng được phân định rõ ràng giữa nhóm có bằng chứng trực tiếp (`DIRECT`), bằng chứng hỗ trợ (`SUPPORTING`) và nhóm thiếu bằng chứng (`MISSING`).
* **Kiến nghị cho nhóm:**
  * Nhóm Ingestion & Retrieval (Hải, Mai): Duy trì cách chia chunk rõ nguồn gốc (provenance) để đảm bảo khi trích xuất không bị lẫn lộn giữa các miền.
  * Nhóm Worker / Grounded Response (Bảo): Khi gặp các case `MISSING` (như M0-10, 11, 12), đảm bảo worker trả về trạng thái `NO_EVIDENCE` và citation rỗng, tuyệt đối không để LLM tự phỏng đoán thông tin ngoài tài liệu.
