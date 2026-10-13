from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ContentSegment(BaseModel):
    """
    Biểu diễn một phân đoạn nội dung có thứ tự và nguồn gốc (provenance).
    Đối với PDF: segment tương ứng với 1 trang gốc (page_number >= 1).
    Đối với TXT/Markdown: segment tương ứng với toàn bộ nội dung hoặc phân đoạn logic gốc.
    """
    model_config = ConfigDict(frozen=True)

    segment_index: int = Field(..., description="Thứ tự phân đoạn, bắt đầu từ 1")
    text: str = Field(..., description="Văn bản của phân đoạn đã được chuẩn hóa an toàn")
    char_count: int = Field(..., description="Số ký tự trong phân đoạn")
    page_number: int | None = Field(
        default=None,
        description="Số trang PDF gốc nếu là PDF, None nếu là TXT hoặc Markdown",
    )


class StructuredExtractionResult(BaseModel):
    """
    Hợp đồng dữ liệu đầu ra có cấu trúc của Ingestion & Extraction Pipeline.
    Được truyền trực tiếp trong bộ nhớ (in-memory) cho bước Chunking tiếp theo.
    """
    model_config = ConfigDict(frozen=True)

    source_id: int = Field(..., description="ID của KnowledgeSource")
    owner_id: int = Field(..., description="ID chủ sở hữu đã được xác minh từ database")
    original_filename: str = Field(..., description="Tên tệp gốc do người dùng tải lên")
    mime_type: str = Field(..., description="MIME type đã xác định của tài liệu")
    text: str = Field(..., description="Toàn bộ nội dung văn bản trích xuất đã chuẩn hóa")
    char_count: int = Field(..., description="Tổng số ký tự trích xuất")
    segments: list[ContentSegment] = Field(
        ...,
        description="Danh sách các phân đoạn nội dung có thứ tự và provenance",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata trích xuất bổ sung (định dạng, số trang, cờ kỹ thuật)",
    )
