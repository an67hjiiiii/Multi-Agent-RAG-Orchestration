# CAPONE-64: Bộ tình huống Simple Ask

- Người phụ trách: Kiều Đức Chung.
- Technical Task: `S2-CHUNG-03`.
- Jira: [CAPONE-64](https://thanhhai2kar5.atlassian.net/browse/CAPONE-64).
- Ngày chuẩn bị: 16/10/2026.

## 1. Mục đích và cách phân nhóm

Bổ sung kết quả mong đợi cho 12 tình huống M0 đã có, để dùng khi kiểm tra Simple Ask. Đây là nội dung cần kiểm tra, chưa phải kết quả hệ thống đã chạy đạt.

Ba miền Security, Database và API/Architecture dựa trên bảng profile tại mục 6.3 của [Research Plan v1.1](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/0add368e92fc95bad5256dcf13ed0c3bfb21fbb7/docs/RESEARCH_PLAN_v1.1.md#63-agent-registry-v%C3%A0-g%C3%A1n-task).

**Phân nhóm áp dụng cho CAPONE-64: `PROPOSED — PENDING_LEADER_CONFIRMATION`.** Jira yêu cầu ba nhóm kỹ thuật nhưng chưa ghi tên hoặc dẫn chiếu Research Plan. Cách phân nhóm này là đề xuất trong tài liệu, chưa thay đổi contract của hệ thống.

M0-01 đến M0-09 được đối chiếu theo ba miền. M0-10 đến M0-12 là các tình huống đối chứng thiếu bằng chứng (negative controls), không phải miền kỹ thuật thứ tư và không bị xem là ngoài phạm vi Simple Ask.

Phân loại phạm vi chức năng đã có trong [PR #21 — CAPONE-63](https://github.com/an67hjiiiii/Multi-Agent-RAG-Orchestration/pull/21). Tài liệu này chỉ bổ sung ý chính cần trả lời và cách đối chiếu, không lặp lại bảng phạm vi đó.

## 2. Dữ liệu dùng để đối chiếu

Giữ nguyên ID và câu hỏi trong [m0_cases.json](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/datasets/calibration/m0_cases.json), commit `5803e783c4d1b58b824d29295898bfd7e0f655fb`.

Corpus cố định gồm:

- [demo_security.md](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/datasets/domain/demo_security.md): xác thực, phân quyền và JWT.
- [demo_database.md](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/datasets/domain/demo_database.md): lưu trữ, index và transaction.
- [demo_api.md](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/datasets/domain/demo_api.md): REST, API contract và phụ thuộc tác vụ.

Chỉ dùng thông tin trong corpus này khi đối chiếu. Nội dung demo không xác nhận cấu hình production hoặc thay thế cơ chế xác thực hiện hành của dự án. Không lấy thông tin từ README hay kiến thức bên ngoài để điền đáp án cho các case thiếu bằng chứng.

## 3. Input và kết quả mong đợi

Cột kết quả mong đợi nêu các ý cần có, không bắt buộc câu trả lời trùng từng chữ. Các ý này được rút từ corpus và chưa phải điểm chấm correctness/faithfulness.

| Case | Miền đề xuất | Input | Kết quả mong đợi | Evidence tham chiếu |
|---|---|---|---|---|
| M0-01 | Security | Authentication verifies what in this system? | Authentication xác minh danh tính. | `present`; `demo_security.md`: “Authentication verifies identity.” |
| M0-02 | Security | What does authorization check before an action is allowed? | Kiểm tra người dùng đã xác thực có quyền thực hiện hành động hay không. | `present`; `demo_security.md`, câu mô tả authorization. |
| M0-03 | Security | Can JWT claims replace server-side authorization policy? | Không. JWT claims không thay thế chính sách phân quyền phía máy chủ. | `present`; `demo_security.md`, câu cuối về JWT claims. |
| M0-04 | Database | Where are user records stored? | Bản ghi người dùng được lưu trong cơ sở dữ liệu quan hệ. | `present`; `demo_database.md`, câu đầu. |
| M0-05 | Database | Which database queries should be reviewed for indexes? | Truy vấn lọc theo các định danh thường dùng cần được xem xét chỉ mục phù hợp. | `present`; `demo_database.md`, câu về queries và indexes. |
| M0-06 | Database | When are transaction boundaries required? | Cần ranh giới transaction cho thao tác ghi nhiều bước phải giữ tính nhất quán; không giới hạn thành trường hợp ghi nhiều bảng. | `present`; `demo_database.md`, câu về multi-step writes. |
| M0-07 | API/Architecture | What kind of endpoints does the service expose? | Dịch vụ cung cấp REST endpoints. | `present`; `demo_api.md`, câu đầu. |
| M0-08 | API/Architecture | What should API contracts define? | Nêu đủ kiểm tra đầu vào, phản hồi lỗi và yêu cầu phân quyền. | `present`; `demo_api.md`, câu về API contracts. |
| M0-09 | API/Architecture | When should architectural dependencies be explicit? | Nêu rõ phụ thuộc khi một tác vụ cần đầu ra do tác vụ khác tạo ra. | `present`; `demo_api.md`, câu cuối. |
| M0-10 | Đối chứng thiếu bằng chứng | What is the production deployment region? | `NO_EVIDENCE`: nêu chưa có thông tin về vùng triển khai; không đoán địa điểm hoặc bịa citation. | `missing`; `expected_source=null`. Cả ba tài liệu không nêu vùng triển khai. |
| M0-11 | Đối chứng thiếu bằng chứng | What is the user's password minimum length? | `NO_EVIDENCE`: nêu chưa có thông tin về độ dài mật khẩu tối thiểu; không tự điền một con số hoặc bịa citation. | `missing`; `expected_source=null`. Tài liệu Security không nêu độ dài mật khẩu. |
| M0-12 | Đối chứng thiếu bằng chứng | What is the monthly SLA percentage? | `NO_EVIDENCE`: nêu chưa có thông tin về tỷ lệ SLA hằng tháng; không đoán tỷ lệ hoặc bịa citation. | `missing`; `expected_source=null`. Cả ba tài liệu không nêu SLA. |

## 4. Cách kiểm tra kết quả

- M0-01 đến M0-09: đối chiếu các ý chính ở bảng và nguồn hỗ trợ. Citation phải trỏ đúng evidence thực sự được cung cấp; không yêu cầu một ID chunk cố định khi chưa có manifest của lần chạy.
- Có evidence không tự động đồng nghĩa với `COMPLETE`. Trạng thái xử lý phải theo contract thực tế; câu trả lời chỉ đáp ứng một phần có thể là `PARTIAL`.
- M0-10 đến M0-12: trong corpus cố định, kỳ vọng `NO_EVIDENCE`, không khẳng định thông tin đang thiếu và không có citation cho thông tin đó. Khi không có evidence hỗ trợ, citations phải rỗng. Nếu hệ thống trả citation cho nội dung không liên quan thì cần ghi nhận để kiểm tra, không coi là trả lời đạt.
- Case thiếu bằng chứng không đại diện cho truy cập trái quyền hoặc lỗi hệ thống. Các ranh giới đó theo [CAPONE-42](https://thanhhai2kar5.atlassian.net/browse/CAPONE-42) và tài liệu phạm vi ở PR #21.
- Khi chạy thực tế, ghi riêng answer, status, citations, phiên bản corpus và nhận xét. Không lấy kết quả mô phỏng điền thành kết quả chạy thật hoặc điểm chấm thủ công.

## 5. Bằng chứng có sẵn và giới hạn

[Báo cáo FakeProvider M0](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/reports/calibration/m0_calibration_fake_20260905T105713Z.json) là kết quả cũ của bộ mô phỏng, được tái sử dụng với nhãn `EXISTING_EVIDENCE / PASS_REPORTED`:

- Có 12 hàng; `locator_valid`, `evidence_behavior_ok` và `source_match` đều là `true`.
- Chín case có bằng chứng được ghi nhận `COMPLETE`; ba case thiếu bằng chứng được ghi nhận `NO_EVIDENCE` với citations rỗng. Đây là quan sát trong báo cáo mô phỏng, không phải cam kết kết quả của LLM thực tế.
- `manual_correctness=UNSCORED` và `manual_faithfulness=UNSCORED` ở cả 12 hàng. Chưa chấm lại hoặc nâng nhãn chất lượng trong tài liệu này.
- Báo cáo không lưu nội dung answer, nên không đủ để xác nhận các ý trả lời ở mục 3 đã được hệ thống đáp ứng.

Mục S2-CHUNG-03 trong [báo cáo Sprint 2](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/reports/sprint2/S2_MAI_CHUNG_QA_REPORT.md) ghi nhận bộ tình huống và bằng chứng wiring có sẵn. Kiểm tra tĩnh fixture/report thuộc S2-MAI-06; tài liệu của Chung tham chiếu kết quả đó và bổ sung kết quả mong đợi, không bổ sung kiểm thử QA.

## 6. Đối chiếu yêu cầu CAPONE-64

| Yêu cầu Jira | Nội dung trong tài liệu | Giới hạn |
|---|---|---|
| Có bộ câu hỏi/input Simple Ask | Giữ 12 input và ID trong bộ M0 ở mục 3. | Không khẳng định 12 case bao phủ mọi tình huống của Simple Ask. |
| Phân theo ba nhóm kỹ thuật | Đề xuất Security, Database, API/Architecture theo Research Plan mục 6.3. | `PROPOSED — PENDING_LEADER_CONFIRMATION`; Jira chưa ghi rõ tên ba nhóm. |
| Có expected outcome cho từng case | Bổ sung ý trả lời, nguồn tham chiếu và cách xử lý thiếu bằng chứng. | Đây là kỳ vọng để đối chiếu, chưa phải kết quả chạy đạt. |
| Dùng được cho kiểm thử và đánh giá | Có input, corpus cố định và hướng dẫn ở mục 4. | Chưa thực hiện kiểm thử luồng tích hợp hoặc chấm ngữ nghĩa trong bước soạn tài liệu. |
| Có tài liệu/bằng chứng scenario | Tài liệu này bổ sung kết quả mong đợi và dẫn dataset, corpus, báo cáo hiện có. | Bản bàn giao trên feature branch; chưa tích hợp hoặc nghiệm thu CAPONE-64. |
