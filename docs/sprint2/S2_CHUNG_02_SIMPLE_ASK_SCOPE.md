# S2-CHUNG-02: Xác thực phạm vi yêu cầu Simple Ask

- Người phụ trách: Kiều Đức Chung.
- Jira: `CAPONE-63` (thuộc Story `CAPONE-42`: Hỏi đáp đơn giản có đối chiếu bằng chứng).
- Phạm vi: `DOC_ONLY` — Xác định ranh giới hỗ trợ của chức năng Simple Ask, đối chiếu bộ kịch bản hiệu chuẩn M0 với yêu cầu nghiệp vụ.
- Mốc bàn giao 16/10/2026: Đã mở [PR #21](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/pull/21) để review; chưa tích hợp vào `dev` tại mốc này.

---

## 1. Nguồn dữ liệu & Căn cứ đối chiếu

Tài liệu tham chiếu bộ tình huống **S2-CHUNG-02 — fixed in-scope and absent-from-corpus cases** trong:
- [`reports/sprint2/S2_MAI_CHUNG_QA_REPORT.md`](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/reports/sprint2/S2_MAI_CHUNG_QA_REPORT.md) thuộc nhánh `sprint2/feature/s2-chung-02-evidence-scope`, commit `5803e783c4d1b58b824d29295898bfd7e0f655fb`, checkpoint Sprint 2 `0add368e92fc95bad5256dcf13ed0c3bfb21fbb7`.
- Bộ 12 kịch bản hiệu chuẩn tại [`datasets/calibration/m0_cases.json`](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/datasets/calibration/m0_cases.json).
- 3 tài liệu tri thức cố định: `demo_security.md`, `demo_database.md`, `demo_api.md`.
- Các quy định cốt lõi của chức năng Simple Ask trong Story Jira `CAPONE-42`.

Phần bổ sung của Chung là đối chiếu 12 tình huống với CAPONE-42 và các contract liên quan, tách phạm vi câu hỏi khỏi trạng thái xử lý, đồng thời ghi rõ ranh giới truy cập dữ liệu theo người dùng. Các câu hỏi M0 và corpus được giữ nguyên để đối chiếu.

Đối chiếu contract ngày 15/10/2026:
- `origin/dev` tại `5bb1f807ca13a5c66fd49e5518bf329f23bc0327` chưa có các file Execution Foundation hoặc Worker dưới đây. [CAPONE-42](https://thanhhai2kar5.atlassian.net/browse/CAPONE-42) yêu cầu xử lý `NO_EVIDENCE` và `FAILED`; [CAPONE-63](https://thanhhai2kar5.atlassian.net/browse/CAPONE-63) yêu cầu xác thực phạm vi, không định nghĩa bộ status mới.
- [PR #5](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/pull/5), commit `b64e935f9f038cf72e193d414e283bb49744690d`: [`ExecutionStatus`](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/blob/b64e935f9f038cf72e193d414e283bb49744690d/backend/app/execution/contracts.py) gồm `COMPLETE`, `PARTIAL`, `NO_EVIDENCE`, `FAILED`, `TIMEOUT`.
- [PR #18](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/pull/18), commit `acceb10a4c7c06ac8ef00d17db004d0e60fb705a`: [`TaskResult.status`](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/blob/acceb10a4c7c06ac8ef00d17db004d0e60fb705a/backend/app/core/types.py) là `str`; [`worker.py`](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/blob/acceb10a4c7c06ac8ef00d17db004d0e60fb705a/backend/app/research/worker.py) và [`vanilla.py`](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/blob/acceb10a4c7c06ac8ef00d17db004d0e60fb705a/backend/app/research/vanilla.py) yêu cầu đầu ra LLM dùng `COMPLETE`, `PARTIAL`, `NO_EVIDENCE`. Có bằng chứng không bảo đảm luôn trả `COMPLETE`: citation không hợp lệ hoặc `COMPLETE` thiếu citation hợp lệ sẽ bị hạ xuống `PARTIAL`.

PR #5 và #18 đều đang **Open, chưa merge** tại lần đối chiếu này. Đây là contract và mã nguồn đang đề xuất tích hợp, chưa phải kết quả xác nhận runtime trên `dev`. `TIMEOUT` có trong enum của PR #5; chưa có căn cứ từ các file Worker đã đọc để gán mọi lỗi hết thời gian thành status này.

---

## 2. Phân loại ranh giới phạm vi Simple Ask (Story CAPONE-42)

Để tránh nhầm lẫn giữa việc **thiếu tài liệu** với việc **hệ thống không hỗ trợ**, cần tách ba khái niệm:
- **Scope classification — phân loại phạm vi:** yêu cầu thuộc hoặc ngoài phạm vi chức năng; đây là nhãn trong tài liệu, không mặc nhiên là runtime status.
- **Evidence availability — mức độ sẵn có của bằng chứng:** bộ tài liệu đang xét có hoặc thiếu thông tin hỗ trợ yêu cầu.
- **Execution status — trạng thái xử lý:** dùng theo contract thực tế. Bảng dưới đối chiếu với Jira và các PR chưa merge đã nêu, không đặt thêm status cho hệ thống.

| Phân nhóm | Bản chất kỹ thuật | Đối chiếu trạng thái xử lý | Trích dẫn (Citations) | Cách xử lý hoặc điểm cần xác nhận |
| :--- | :--- | :--- | :--- | :--- |
| **Nhóm 1: Trong phạm vi — Có bằng chứng** *(In-Scope, Evidence Present)* | Câu hỏi tra cứu miền tri thức hợp lệ; tập tài liệu người dùng tải lên có chứa đoạn trích (chunk) liên quan trực tiếp (`DIRECT`) hoặc hỗ trợ (`SUPPORTING`). | Theo đầu ra dự kiến trong PR #18: có thể `COMPLETE`, `PARTIAL` hoặc `NO_EVIDENCE` tùy mức đáp ứng; không suy ra `COMPLETE` chỉ vì có chunk. | Chỉ giữ citation hợp lệ trỏ đến evidence được cung cấp. `COMPLETE` thiếu citation hợp lệ bị hạ xuống `PARTIAL` trong PR #18. | Trả lời trong giới hạn bằng chứng thực sự hỗ trợ; không khẳng định chất lượng ngữ nghĩa từ status hoặc mã citation. |
| **Nhóm 2: Trong phạm vi — Thiếu bằng chứng** *(In-Scope, Evidence Missing)* | Câu hỏi tra cứu hợp lệ nhưng không có evidence liên quan; hoặc evidence chỉ hỗ trợ một phần yêu cầu. | PR #18 trả `NO_EVIDENCE` khi danh sách evidence rỗng; trường hợp chỉ đáp ứng một phần có thể là `PARTIAL`. | Không có evidence thì citations rỗng. `PARTIAL` có thể giữ citation hợp lệ cho phần được hỗ trợ; không buộc mọi trường hợp thiếu thông tin đều có citation rỗng. | Nêu thông tin còn thiếu, không tự suy diễn hoặc bịa trích dẫn. |
| **Nhóm 3: Phạm vi loại trừ đề xuất** *(Proposed Out-of-Scope Requests)* | Ví dụ yêu cầu thay đổi dữ liệu, workflow đa agent hoặc chat không gắn với tài liệu; chi tiết ở mục 4. | Chưa có status chính thức được xác nhận cho nhãn phạm vi này; `PROPOSED / PENDING_LEADER_CONFIRMATION` là ghi chú trong tài liệu. | Cách biểu diễn kết quả chờ contract được chốt; không tự quy định schema phản hồi. | Leader xác nhận phạm vi loại trừ và cách xử lý trước khi triển khai. Truy cập trái quyền là ranh giới bảo mật riêng ở mục 4. |
| **Nhóm 4: Lỗi xử lý hệ thống** *(Processing Failure)* | Lỗi kỹ thuật có thể xảy ra trong quá trình xử lý, khác với thiếu evidence hoặc ngoài phạm vi. | `FAILED` được CAPONE-42 yêu cầu và có trong PR #5. `TIMEOUT` chỉ được xác minh trong enum PR #5, không tự ánh xạ mọi lỗi cụ thể sang status này. | Theo kết quả thực tế và contract khi tích hợp; không tự đặt thêm quy tắc citation cho lỗi. | Xử lý lỗi theo luồng được tích hợp; không coi lỗi kỹ thuật là kết luận về phạm vi câu hỏi. |

> **Nguyên tắc quan trọng:** *"Thiếu bằng chứng trong bộ tài liệu M0"* **không đồng nghĩa** với *"Nằm ngoài phạm vi của chức năng Simple Ask"*. Bộ kịch bản M0 là tập kiểm thử nhỏ (calibration fixture). Khi người dùng hỏi một câu hỏi hợp lệ mà tài liệu chưa nạp (ví dụ hỏi về vùng triển khai, quy định mật khẩu), hệ thống phải nhận diện được tình trạng thiếu bằng chứng và trả về `NO_EVIDENCE`. Đó là chức năng bảo vệ tính trung thực (faithfulness), hoàn toàn nằm trong phạm vi nghiệp vụ được thiết kế của Simple Ask.

---

## 3. Đối chiếu chi tiết 12 kịch bản M0 Calibration

Dưới đây là bảng đối chiếu 12 kịch bản kiểm thử cố định trong `m0_cases.json` với phân loại phạm vi:

| Mã case | Câu hỏi tra cứu | Miền tài liệu | Bằng chứng kỳ vọng | Phân loại phạm vi | Ghi chú xử lý |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `M0-01` | Authentication verifies what in this system? | Security (`demo_security.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Đoạn tài liệu nêu trực tiếp việc xác minh danh tính (`DIRECT`). |
| `M0-02` | What does authorization check before an action is allowed? | Security (`demo_security.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Đoạn tài liệu nêu việc kiểm tra người dùng đã xác thực có quyền thực hiện hành động hay không (`DIRECT`). |
| `M0-03` | Can JWT claims replace server-side authorization policy? | Security (`demo_security.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Ràng buộc chính sách phía server so với claims (`SUPPORTING`). |
| `M0-04` | Where are user records stored? | Database (`demo_database.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Bảng người dùng trong cơ sở dữ liệu quan hệ (`DIRECT`). |
| `M0-05` | Which database queries should be reviewed for indexes? | Database (`demo_database.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Tiêu chí đánh giá truy vấn cần đánh chỉ mục (`DIRECT`). |
| `M0-06` | When are transaction boundaries required? | Database (`demo_database.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Cần ranh giới transaction cho thao tác ghi nhiều bước phải giữ tính nhất quán (`DIRECT`). |
| `M0-07` | What kind of endpoints does the service expose? | API (`demo_api.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Các REST endpoints chuẩn của dịch vụ (`DIRECT`). |
| `M0-08` | What should API contracts define? | API (`demo_api.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Ràng buộc dữ liệu đầu vào và phản hồi lỗi (`SUPPORTING`). |
| `M0-09` | When should architectural dependencies be explicit? | Architecture (`demo_api.md`) | `present` | **Nhóm 1: Trong phạm vi, có bằng chứng** | Phụ thuộc kiến trúc module rõ ràng (`DIRECT`). |
| `M0-10` | What is the production deployment region? | Chưa nạp / Không có | `missing` | **Nhóm 2: Trong phạm vi, thiếu bằng chứng** | Negative control: Tài liệu M0 không có thông tin vùng triển khai. Phải trả về `NO_EVIDENCE`. |
| `M0-11` | What is the user's password minimum length? | Chưa nạp / Không có | `missing` | **Nhóm 2: Trong phạm vi, thiếu bằng chứng** | Negative control: Tài liệu M0 không nêu độ dài mật khẩu. Phải trả về `NO_EVIDENCE`. |
| `M0-12` | What is the monthly SLA percentage? | Chưa nạp / Không có | `missing` | **Nhóm 2: Trong phạm vi, thiếu bằng chứng** | Negative control: Tài liệu M0 không nêu cam kết SLA. Phải trả về `NO_EVIDENCE`. |

---

## 4. Ranh giới bảo mật và phạm vi loại trừ đề xuất

Story `CAPONE-42` xác nhận luồng hỏi đáp dựa trên evidence đúng người dùng, nhưng không liệt kê đầy đủ các yêu cầu ngoài phạm vi hay status dành cho chúng. Các mục 1, 3 và 4 dưới đây là **`PROPOSED / PENDING_LEADER_CONFIRMATION` — đề xuất, chờ leader xác nhận**. Mục 2 là ràng buộc bảo mật đã có căn cứ từ story, không phải một loại thiếu bằng chứng.

1. **Yêu cầu thực thi thay đổi hệ thống (Action / Mutation Requests):**
   - *Ví dụ:* "Hãy xóa tài liệu demo_security.md", "Đổi mật khẩu người dùng admin", "Tạo thêm một bảng mới trong database".
   - *Căn cứ đề xuất:* CAPONE-42 mô tả chức năng hỏi đáp theo evidence, chưa xác nhận chức năng thực thi các lệnh thay đổi này. Không tự kết luận quyền ghi hoặc mã phản hồi của runtime.
2. **Yêu cầu vi phạm phân quyền sở hữu dữ liệu (Cross-tenant / Unauthorized Data Access):**
   - *Ví dụ:* Người dùng A yêu cầu tra cứu tài liệu riêng tư của người dùng B mà không có quyền chia sẻ.
   - *Căn cứ đã xác nhận:* CAPONE-42 yêu cầu Retrieval dùng đúng dữ liệu người dùng và không làm lộ dữ liệu giữa các người dùng. Phải tuân theo auth/owner isolation (xác thực và cách ly dữ liệu theo chủ sở hữu); không coi truy cập trái quyền là `NO_EVIDENCE`. Mã lỗi HTTP hoặc execution status phải theo contract bảo mật thực tế, không tự ấn định trong tài liệu này.
3. **Yêu cầu lập kế hoạch đa bước phức tạp (Multi-step Agentic Workflow):**
   - *Ví dụ:* "Phân tích toàn bộ hệ thống, phân rã thành các task cho 5 người và lên lịch trình chi tiết".
   - *Căn cứ đề xuất:* CAPONE-42 chưa xác nhận việc Simple Ask thực thi workflow điều phối nhiều agent. Cần leader chốt ranh giới; không tự coi mọi câu hỏi phân tích nhiều bước đều ngoài phạm vi.
4. **Trò chuyện mở không gắn với tài liệu (Unconstrained Open-domain Chat):**
   - *Ví dụ:* Hỏi dự báo thời tiết, viết văn, giải toán không liên quan đến tài liệu dự án.
   - *Căn cứ đề xuất:* CAPONE-42 yêu cầu câu trả lời dựa trên evidence. Cần leader xác nhận cách xử lý yêu cầu trò chuyện không dựa trên tài liệu; không đồng nhất các ví dụ này với ba case M0 thiếu evidence.

---

## 5. Bằng chứng kiểm tra có sẵn (`EXISTING_EVIDENCE`)

- Kết quả kiểm thử trên bộ dữ liệu M0 tại commit `5803e783c4d1b58b824d29295898bfd7e0f655fb` được ghi nhận với nhãn `EXISTING_EVIDENCE` / `PASS_REPORTED`:
  - Kiểm tra tự động 12 dòng: `locator_valid=true`, `evidence_behavior_ok=true`, `source_match=true`.
  - Cả 3 case thiếu bằng chứng (`M0-10`, `M0-11`, `M0-12`) đều ghi nhận phản hồi `NO_EVIDENCE` với citations rỗng.
- **Ranh giới xác thực:** Kết quả tự động trên chỉ chứng minh đường truyền dữ liệu (wiring evidence) và hành vi phân loại theo quy tắc tĩnh. Việc đánh giá câu trả lời thực tế có chính xác và trung thực về mặt ngữ nghĩa hay không vẫn ở trạng thái `UNSCORED` và thuộc về trách nhiệm `human semantic review` của nhóm nghiên cứu.
