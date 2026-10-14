import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

# Regex nhận diện nếu chuỗi chỉ gồm ký tự khoảng trắng (ASCII hoặc Unicode)
_WHITESPACE_ONLY_REGEX = re.compile(r"^\s*$", re.UNICODE)


class ChunkCreateInput(BaseModel):
    """
    DTO đầu vào cho một Chunk do module Chunking tạo ra.
    Ràng buộc nghiêm ngặt:
    - chunk_index >= 0
    - content không rỗng hoặc toàn khoảng trắng (kể cả Unicode whitespace)
    - page_number >= 1 khi có
    - start_offset và end_offset đồng thời NULL hoặc đồng thời có giá trị với end > start.
    """
    model_config = ConfigDict(frozen=True)

    chunk_index: int = Field(..., ge=0, description="Thứ tự chunk trong tài liệu, bắt đầu từ 0")
    content: str = Field(..., min_length=1, description="Nội dung văn bản của chunk")
    page_number: int | None = Field(default=None, ge=1, description="Số trang PDF gốc bắt đầu từ 1 nếu có")
    section: str | None = Field(default=None, max_length=255, description="Tiêu đề mục hoặc heading nếu xác định được")
    start_offset: int | None = Field(default=None, ge=0, description="Chỉ số ký tự bắt đầu trong văn bản nguồn chuẩn hóa")
    end_offset: int | None = Field(default=None, gt=0, description="Chỉ số ký tự kết thúc trong văn bản nguồn chuẩn hóa")

    @field_validator("content")
    @classmethod
    def validate_content_not_whitespace(cls, v: str) -> str:
        if not v or _WHITESPACE_ONLY_REGEX.match(v):
            raise ValueError("Nội dung chunk không được để trống hoặc chỉ chứa khoảng trắng")
        return v

    @model_validator(mode="after")
    def validate_offset_pair(self) -> "ChunkCreateInput":
        start = self.start_offset
        end = self.end_offset
        if (start is None and end is not None) or (start is not None and end is None):
            raise ValueError("start_offset và end_offset phải đồng thời có giá trị hoặc đồng thời bằng None")
        if start is not None and end is not None and end <= start:
            raise ValueError("end_offset phải lớn hơn start_offset")
        return self


class KnowledgeChunkRead(BaseModel):
    """
    DTO đầu ra khi đọc dữ liệu một Chunk từ database.
    char_count được tính động từ len(content), không phụ thuộc vào cột database.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID duy nhất của Chunk")
    source_id: int = Field(..., description="ID của KnowledgeSource")
    chunk_index: int = Field(..., description="Thứ tự của Chunk trong tài liệu")
    content: str = Field(..., description="Nội dung văn bản")
    page_number: int | None = Field(default=None, description="Trang PDF gốc nếu có")
    section: str | None = Field(default=None, description="Tiêu đề mục nếu có")
    start_offset: int | None = Field(default=None, description="Offset bắt đầu")
    end_offset: int | None = Field(default=None, description="Offset kết thúc")

    @computed_field
    @property
    def char_count(self) -> int:
        return len(self.content)


class QdrantChunkPayload(BaseModel):
    """
    Hợp đồng dữ liệu metadata gửi tới Qdrant Vector Store.
    owner_id bắt buộc phải được lấy từ KnowledgeSource trong database,
    tuyệt đối không nhận từ client.
    """
    model_config = ConfigDict(frozen=True)

    chunk_id: int = Field(..., description="ID của Chunk trong PostgreSQL")
    source_id: int = Field(..., description="ID của KnowledgeSource trong PostgreSQL")
    owner_id: int = Field(..., description="Owner ID đã xác minh của KnowledgeSource")
    chunk_index: int = Field(..., description="Thứ tự chunk")
    content: str = Field(..., description="Nội dung văn bản chunk")
    page_number: int | None = Field(default=None, description="Số trang PDF gốc nếu có")
    section: str | None = Field(default=None, description="Heading/Section nếu có")
    start_offset: int | None = Field(default=None, description="Offset bắt đầu")
    end_offset: int | None = Field(default=None, description="Offset kết thúc")
