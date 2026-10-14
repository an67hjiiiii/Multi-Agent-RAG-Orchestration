# S2-CHUNG-01: Tiêu chí đánh giá bằng chứng truy xuất

- Người phụ trách: Kiều Đức Chung.
- Jira: `CAPONE-62` theo thông tin Planning Poker được bàn giao; chưa xác minh trực tiếp trên Jira.
- Phạm vi: `DOC_ONLY` — bảng tiêu chí để đánh giá tài liệu tìm được, chưa có chức năng tự chấm điểm.

## Nguồn

Chuyển riêng mục **S2-CHUNG-01 — evidence relevance rubric** từ
[`reports/sprint2/S2_MAI_CHUNG_QA_REPORT.md`](https://github.com/an67hjiiiii/Multi-Agent-Orchestratio-/blob/5803e783c4d1b58b824d29295898bfd7e0f655fb/reports/sprint2/S2_MAI_CHUNG_QA_REPORT.md),
nhánh `sprint2/feature/s2-chung-01-relevance-rubric`, commit
`5803e783c4d1b58b824d29295898bfd7e0f655fb`.

## Bảng tiêu chí

Evidence (bằng chứng) ở đây là đoạn tài liệu được tìm để hỗ trợ câu trả lời.
Các mức dưới đây được xét trong bộ tài liệu cố định đang đánh giá. Bảng này
không dùng AI để tự chấm và không coi mã đoạn tài liệu hợp lệ là bằng chứng
cho thấy câu trả lời đã đúng.

| Mức | Ý nghĩa | Cách xử lý |
| --- | --- | --- |
| `DIRECT` — hỗ trợ trực tiếp | Đoạn tài liệu nêu trực tiếp sự kiện hoặc quy tắc được hỏi. | Có thể dùng làm bằng chứng cho nhận định; vẫn cần người review đánh giá nội dung. |
| `SUPPORTING` — hỗ trợ một phần | Đoạn tài liệu cung cấp định nghĩa hoặc ràng buộc liên quan nhưng chưa trả lời đầy đủ yêu cầu. | Có thể hỗ trợ câu trả lời một phần; không coi là đã đáp ứng đầy đủ yêu cầu. |
| `NOT_RELEVANT` — không liên quan | Đoạn tài liệu có sẵn nhưng không hỗ trợ thông tin được hỏi, dù có thể cùng chủ đề chung. | Không dùng để chứng minh nhận định. |
| `MISSING` — thiếu bằng chứng | Bộ tài liệu cố định không có đoạn hỗ trợ thông tin được hỏi. | Trả về `NO_EVIDENCE` (không có bằng chứng) hoặc `PARTIAL` (chỉ đáp ứng một phần) tùy trường hợp; không tự suy ra hoặc bịa trích dẫn. |
| `UNSCORED` — chưa được chấm | Đã có thông tin kiểm tra mã tham chiếu hoặc kiểm tra tự động, nhưng con người chưa đánh giá tính đúng đắn hoặc mức độ bám sát tài liệu. | Không dùng để kết luận chất lượng nội dung hoặc đạt mốc nghiệm thu. |

## Phân biệt các nội dung đánh giá

- **Locator validity — mã tham chiếu hợp lệ:** mã này có trỏ tới một đoạn tài liệu đã được cung cấp không?
- **Evidence relevance — mức độ liên quan của bằng chứng:** đoạn tài liệu đó có hỗ trợ yêu cầu đang xét không?
- **Correctness — tính đúng đắn:** nội dung câu trả lời có đúng không?
- **Faithfulness — mức độ bám sát tài liệu:** câu trả lời có được tài liệu hỗ trợ không?

Tính đúng đắn và mức độ bám sát tài liệu là hai nội dung đánh giá riêng của
người review. Việc chuyển bảng tiêu chí này không có nghĩa là đã thực hiện
human semantic review (con người đánh giá chất lượng nội dung).
