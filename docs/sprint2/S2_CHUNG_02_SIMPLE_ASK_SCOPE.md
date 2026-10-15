# S2-CHUNG-02: Xác thực phạm vi yêu cầu Simple Ask

- Người phụ trách: Kiều Đức Chung.
- Jira: `CAPONE-63` (thuộc Story `CAPONE-42`: Hỏi đáp đơn giản có đối chiếu bằng chứng).
- Phạm vi: `DOC_ONLY` — Xác định ranh giới hỗ trợ của chức năng Simple Ask, đối chiếu bộ kịch bản hiệu chuẩn M0 với yêu cầu nghiệp vụ.
- Trạng thái: `LOCAL_PREPARATION` — Chuẩn bị nhánh local, chờ phê duyệt triển khai sớm để mở PR.

---

## 1. Nguồn dữ liệu & Căn cứ đối chiếu

Tài liệu được chuyển và chuẩn hóa từ mục **S2-CHUNG-02 — fixed in-scope and absent-from-corpus cases** trong:
- [`reports/sprint2/S2_MAI_CHUNG_QA_REPORT.md`](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/reports/sprint2/S2_MAI_CHUNG_QA_REPORT.md) thuộc nhánh `sprint2/feature/s2-chung-02-evidence-scope`, commit `5803e783c4d1b58b824d29295898bfd7e0f655fb`, checkpoint Sprint 2 `0add368e92fc95bad5256dcf13ed0c3bfb21fbb7`.
- Bộ 12 kịch bản hiệu chuẩn tại [`datasets/calibration/m0_cases.json`](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/datasets/calibration/m0_cases.json).
- 3 tài liệu tri thức cố định: `demo_security.md`, `demo_database.md`, `demo_api.md`.
- Các quy định cốt lõi của chức năng Simple Ask trong Story Jira `CAPONE-42`.

---

## 2. Phân loại ranh giới phạm vi Simple Ask (Story CAPONE-42)

Để tránh nhầm lẫn giữa việc **thiếu tài liệu** với việc **hệ thống không hỗ trợ**, chức năng Simple Ask được phân định thành 4 nhóm tình huống rõ ràng:

| Phân nhóm | Bản chất kỹ thuật | Trạng thái phản hồi | Trích dẫn (Citations) | Hành vi yêu cầu của hệ thống |
| :--- | :--- | :--- | :--- | :--- |
| **Nhóm 1: Trong phạm vi — Có bằng chứng** *(In-Scope, Evidence Present)* | Câu hỏi tra cứu miền tri thức hợp lệ; tập tài liệu người dùng tải lên có chứa đoạn trích (chunk) liên quan trực tiếp (`DIRECT`) hoặc hỗ trợ (`SUPPORTING`). | `SUCCESS` | Có ít nhất 1 citation hợp lệ trỏ đúng chunk ID. | Sinh câu trả lời bám sát tài liệu (grounded response), dẫn nguồn rõ ràng. |
| **Nhóm 2: Trong phạm vi — Thiếu bằng chứng** *(In-Scope, Evidence Missing)* | Câu hỏi tra cứu miền tri thức hợp lệ, nhưng bộ tài liệu hiện tại **không chứa thông tin trả lời**. | `NO_EVIDENCE` (hoặc `PARTIAL`) | Rỗng (`[]`), tuyệt đối không bịa citation. | Thông báo rõ ràng tài liệu chưa có thông tin; không tự suy diễn hoặc bịa đặt (hallucination). |
| **Nhóm 3: Ngoài phạm vi chức năng** *(Out-of-Scope Requests)* | Yêu cầu không thuộc mục đích tra cứu tri thức hoặc vượt quá thẩm quyền của Simple Ask (thay đổi dữ liệu, truy cập trái quyền, chat mở không căn cứ). | `OUT_OF_SCOPE` | Rỗng (`[]`). | Từ chối thực thi hoặc hướng dẫn người dùng đặt câu hỏi tra cứu phù hợp. |
| **Nhóm 4: Lỗi xử lý hệ thống** *(Processing Failure)* | Lỗi runtime (Ollama timeout, tràn VRAM/RAM, lỗi kết nối cơ sở dữ liệu PostgreSQL/Qdrant). | `FAILED` | Không áp dụng. | Ghi nhận trace/log lỗi; phản hồi thông báo hệ thống bận/thử lại; không đánh đồng với ngoài phạm vi. |

> **Nguyên tắc quan trọng:** *"Thiếu bằng chứng trong bộ tài liệu M0"* **không đồng nghĩa** với *"Nằm ngoài phạm vi của chức năng Simple Ask"*. Bộ kịch bản M0 là tập kiểm thử nhỏ (calibration fixture). Khi người dùng hỏi một câu hỏi hợp lệ mà tài liệu chưa nạp (ví dụ hỏi về vùng triển khai, quy định mật khẩu), hệ thống phải nhận diện được tình trạng thiếu bằng chứng và trả về `NO_EVIDENCE`. Đó là chức năng bảo vệ tính trung thực (faithfulness), hoàn toàn nằm trong phạm vi nghiệp vụ được thiết kế của Simple Ask.

---

## 3. Đối chiếu chi tiết 12 kịch bản M0 Calibration

Dưới đây là bảng đối chiếu 12 kịch bản kiểm thử cố định trong `m0_cases.json` với phân loại phạm vi:

| Mã case | Câu hỏi tra cứu | Miền tài liệu | Bằng chứng kỳ vọng | Phân loại phạm vi | Ghi chú xử lý |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `M0-01` | Authentication verifies what in this system? | Security (`demo_security.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Đoạn tài liệu nêu trực tiếp việc xác minh danh tính (`DIRECT`). |
| `M0-02` | What does authorization check before an action is allowed? | Security (`demo_security.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Đoạn tài liệu nêu quyền hạn và vai trò người dùng (`DIRECT`). |
| `M0-03` | Can JWT claims replace server-side authorization policy? | Security (`demo_security.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Ràng buộc chính sách phía server so với claims (`SUPPORTING`). |
| `M0-04` | Where are user records stored? | Database (`demo_database.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Bảng người dùng trong cơ sở dữ liệu quan hệ (`DIRECT`). |
| `M0-05` | Which database queries should be reviewed for indexes? | Database (`demo_database.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Tiêu chí đánh giá truy vấn cần đánh chỉ mục (`DIRECT`). |
| `M0-06` | When are transaction boundaries required? | Database (`demo_database.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Ranh giới transaction khi cập nhật nhiều bảng (`DIRECT`). |
| `M0-07` | What kind of endpoints does the service expose? | API (`demo_api.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Các REST endpoints chuẩn của dịch vụ (`DIRECT`). |
| `M0-08` | What should API contracts define? | API (`demo_api.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Ràng buộc dữ liệu đầu vào và phản hồi lỗi (`SUPPORTING`). |
| `M0-09` | When should architectural dependencies be explicit? | Architecture (`demo_api.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Phụ thuộc kiến trúc module rõ ràng (`DIRECT`). |
| `M0-10` | What is the production deployment region? | Chưa nạp / Không có | `missing` | **Nhóm 2: Trong phạm vi, thiếu bằng chứng** | Negative control: Tài liệu M0 không có thông tin vùng triển khai. Phải trả về `NO_EVIDENCE`. |
| `M0-11` | What is the user's password minimum length? | Chưa nạp / Không có | `missing` | **Nhóm 2: Trong phạm vi, thiếu bằng chứng** | Negative control: Tài liệu M0 không nêu độ dài mật khẩu. Phải trả về `NO_EVIDENCE`. |
| `M0-12` | What is the monthly SLA percentage? | Chưa nạp / Không có | `missing` | **Nhóm 2: Trong phạm vi, thiếu bằng chứng** | Negative control: Tài liệu M0 không nêu cam kết SLA. Phải trả về `NO_EVIDENCE`. |

---

## 4. Các trường hợp thực sự NẰM NGOÀI phạm vi chức năng (Out-of-Scope)

Theo Story `CAPONE-42`, Simple Ask được thiết kế thuần túy cho bài toán **đọc và tra cứu tri thức đã nạp (Read-only Grounded RAG)**. Các trường hợp sau đây xác định là **nằm ngoài phạm vi hỗ trợ**:

1. **Yêu cầu thực thi thay đổi hệ thống (Action / Mutation Requests):**
   - *Ví dụ:* "Hãy xóa tài liệu demo_security.md", "Đổi mật khẩu người dùng admin", "Tạo thêm một bảng mới trong database".
   - *Lý do:* Simple Ask không có quyền thao tác ghi hoặc thay đổi cơ sở dữ liệu/tài liệu.
2. **Yêu cầu vi phạm phân quyền sở hữu dữ liệu (Cross-tenant / Unauthorized Data Access):**
   - *Ví dụ:* Người dùng A yêu cầu tra cứu tài liệu riêng tư của người dùng B mà không có quyền chia sẻ.
   - *Lý do:* CAPONE-42 quy định nghiêm ngặt quyền sở hữu (`owner_user_id`), chỉ truy xuất tài liệu thuộc quyền của người dùng hiện tại.
3. **Yêu cầu lập kế hoạch đa bước phức tạp (Multi-step Agentic Workflow):**
   - *Ví dụ:* "Phân tích toàn bộ hệ thống, phân rã thành các task cho 5 người và lên lịch trình chi tiết".
   - *Lý do:* Đây là phạm vi của module Planning và Multi-Agent Orchestration (sẽ phát triển ở các Sprint sau), vượt quá khả năng của 1 lượt Simple Ask.
4. **Trò chuyện mở không gắn với tài liệu (Unconstrained Open-domain Chat):**
   - *Ví dụ:* Hỏi dự báo thời tiết, viết văn, giải toán không liên quan đến tài liệu dự án.
   - *Lý do:* Hệ thống tập trung tối ưu tài nguyên cho RAG cục bộ trên máy hạn chế, không hướng tới thay thế trợ lý đa năng mở.

---

## 5. Bằng chứng kiểm tra có sẵn (`EXISTING_EVIDENCE`)

- Kết quả kiểm thử trên bộ dữ liệu M0 tại commit `5803e783c4d1b58b824d29295898bfd7e0f655fb` được ghi nhận với nhãn `EXISTING_EVIDENCE` / `PASS_REPORTED`:
  - Kiểm tra tự động 12 dòng: `locator_valid=true`, `evidence_behavior_ok=true`, `source_match=true`.
  - Cả 3 case thiếu bằng chứng (`M0-10`, `M0-11`, `M0-12`) đều ghi nhận phản hồi `NO_EVIDENCE` với citations rỗng.
- **Ranh giới xác thực:** Kết quả tự động trên chỉ chứng minh đường truyền dữ liệu (wiring evidence) và hành vi phân loại theo quy tắc tĩnh. Việc đánh giá câu trả lời thực tế có chính xác và trung thực về mặt ngữ nghĩa hay không vẫn ở trạng thái `UNSCORED` và thuộc về trách nhiệm `human semantic review` của nhóm nghiên cứu.
