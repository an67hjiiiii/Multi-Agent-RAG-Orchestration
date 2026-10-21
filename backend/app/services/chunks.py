import logging
from typing import Any
from sqlalchemy.orm import Session

from app.models.chunk import KnowledgeChunk
from app.models.knowledge import KnowledgeSource
from app.schemas.chunk import ChunkCreateInput, KnowledgeChunkRead, QdrantChunkPayload

logger = logging.getLogger(__name__)


class ChunkServiceError(Exception):
    """Lỗi cơ sở cho các thao tác quản lý KnowledgeChunk."""

    def __init__(self, message: str, code: str = "CHUNK_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class ChunkNotFoundError(ChunkServiceError):
    """Không tìm thấy chunk hoặc người dùng không có quyền truy cập."""

    def __init__(self, message: str = "Không tìm thấy đoạn trích hoặc bạn không có quyền truy cập"):
        super().__init__(message, code="NOT_FOUND")


class ChunkOwnershipError(ChunkServiceError):
    """Người dùng không sở hữu tài liệu nguồn của chunk."""

    def __init__(self, message: str = "Bạn không có quyền truy cập hoặc chỉnh sửa tài liệu này"):
        super().__init__(message, code="FORBIDDEN")


class ChunkLifecycleError(ChunkServiceError):
    """Trạng thái hiện tại của KnowledgeSource không cho phép thay thế hoặc trích xuất chunk."""

    def __init__(self, message: str = "Trạng thái tài liệu không hợp lệ để tạo hoặc thay thế chunk"):
        super().__init__(message, code="INVALID_LIFECYCLE_STATE")


class ChunkValidationError(ChunkServiceError):
    """Dữ liệu tập chunk đầu vào không hợp lệ."""

    def __init__(self, message: str = "Dữ liệu tập chunk đầu vào không hợp lệ"):
        super().__init__(message, code="VALIDATION_ERROR")


def replace_source_chunks(
    db: Session,
    source_id: int,
    trusted_owner_id: int,
    chunks_in: list[ChunkCreateInput],
) -> list[KnowledgeChunkRead]:
    """
    Thay thế nguyên tử toàn bộ tập KnowledgeChunk của một KnowledgeSource:
    1. Pre-validation:
       - Danh sách chunks_in không được rỗng (từ chối empty batch).
       - Thứ tự chunk_index phải bắt đầu từ 0 và liên tục: 0, 1, 2, ..., N-1.
    2. Kiểm tra quyền sở hữu và khóa dòng KnowledgeSource:
       - Truy vấn KnowledgeSource với filter(id == source_id, owner_id == trusted_owner_id).
       - Khóa dòng với with_for_update() khi database hỗ trợ (trên PostgreSQL).
       - Nếu không tìm thấy: ném ChunkNotFoundError (chống IDOR).
    3. Lifecycle Guard:
       - Chỉ cho phép khi source.status == 'EXTRACTED' (hoặc 'PROCESSING' nếu có).
       - Tuyệt đối từ chối nếu source.status == 'READY' hoặc 'FAILED' hoặc 'UPLOADED' chưa extract.
    4. Xóa và Chèn trong cùng Transaction:
       - Xóa toàn bộ chunks cũ: DELETE FROM knowledge_chunks WHERE source_id = :source_id.
       - Chèn toàn bộ chunks mới.
       - Caller sở hữu commit / rollback. Hàm thực hiện db.flush() để sinh ID và kích hoạt DB constraints.
    """
    # 1. Pre-validation
    if not chunks_in:
        raise ChunkValidationError("Danh sách chunk không được để trống (từ chối empty batch)")

    # Kiểm tra tính duy nhất và liên tục của chunk_index (0..N-1)
    indices = [c.chunk_index for c in chunks_in]
    expected_indices = list(range(len(chunks_in)))
    if indices != expected_indices:
        raise ChunkValidationError(
            f"Thứ tự chunk_index phải bắt đầu từ 0 và liên tục không ngắt quãng (nhận được: {indices}, kỳ vọng: {expected_indices})"
        )

    # 2. Truy vấn và khóa dòng KnowledgeSource theo trusted_owner_id
    # Lưu ý: with_for_update() hoạt động trên PostgreSQL (sẽ kiểm tra trong Phase 2B)
    source_query = (
        db.query(KnowledgeSource)
        .filter(
            KnowledgeSource.id == source_id,
            KnowledgeSource.owner_id == trusted_owner_id,
        )
    )

    # Áp dụng with_for_update nếu dialect hỗ trợ (PostgreSQL / MySQL)
    if db.bind and db.bind.dialect.name == "postgresql":
        source_query = source_query.with_for_update()

    source = source_query.first()

    if not source:
        logger.warning(
            "Yêu cầu thay thế chunk không hợp lệ (sai source hoặc owner): source_id=%s, owner_id=%s",
            source_id,
            trusted_owner_id,
        )
        raise ChunkNotFoundError("Không tìm thấy tài liệu hoặc bạn không có quyền truy cập")

    # 3. Lifecycle Guard
    # Chỉ nhận Source đã EXTRACTED (đã hoàn thành bước bóc tách văn bản)
    if source.status != "EXTRACTED":
        logger.warning(
            "Từ chối thay thế chunk: source_id=%s có trạng thái status=%s (yêu cầu EXTRACTED)",
            source_id,
            source.status,
        )
        raise ChunkLifecycleError(
            f"Tài liệu đang ở trạng thái '{source.status}', chỉ tài liệu có trạng thái 'EXTRACTED' mới được tạo chunks"
        )

    # 4. Atomic Replacement: Xóa cũ và Chèn mới
    # Xóa toàn bộ chunks cũ của source_id này
    db.query(KnowledgeChunk).filter(KnowledgeChunk.source_id == source_id).delete(synchronize_session=False)

    # Chèn các chunks mới
    new_chunk_models: list[KnowledgeChunk] = []
    for c_in in chunks_in:
        chunk_obj = KnowledgeChunk(
            source_id=source.id,
            chunk_index=c_in.chunk_index,
            content=c_in.content,
            page_number=c_in.page_number,
            section=c_in.section,
            start_offset=c_in.start_offset,
            end_offset=c_in.end_offset,
        )
        db.add(chunk_obj)
        new_chunk_models.append(chunk_obj)

    # Flush vào database để sinh ID và xác thực DB constraints mà không tự commit transaction của caller
    db.flush()

    return [KnowledgeChunkRead.model_validate(c) for c in new_chunk_models]


def get_chunk_by_id(
    db: Session,
    chunk_id: int,
    trusted_owner_id: int,
) -> KnowledgeChunkRead:
    """
    Đọc một KnowledgeChunk theo ID và xác minh quyền sở hữu:
    - Bắt buộc JOIN với KnowledgeSource và lọc KnowledgeSource.owner_id == trusted_owner_id.
    - Nếu không tìm thấy hoặc sai owner: ném ChunkNotFoundError.
    """
    chunk = (
        db.query(KnowledgeChunk)
        .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
        .filter(
            KnowledgeChunk.id == chunk_id,
            KnowledgeSource.owner_id == trusted_owner_id,
        )
        .first()
    )

    if not chunk:
        logger.warning(
            "Không tìm thấy chunk hoặc sai owner: chunk_id=%s, owner_id=%s",
            chunk_id,
            trusted_owner_id,
        )
        raise ChunkNotFoundError("Không tìm thấy đoạn trích hoặc bạn không có quyền truy cập")

    return KnowledgeChunkRead.model_validate(chunk)


def list_chunks_for_source(
    db: Session,
    source_id: int,
    trusted_owner_id: int,
) -> list[KnowledgeChunkRead]:
    """
    Liệt kê toàn bộ các chunks thuộc về một KnowledgeSource theo thứ tự chunk_index:
    - Xác minh quyền sở hữu tài liệu nguồn trước khi đọc.
    - Sắp xếp tăng dần theo chunk_index.
    """
    source = (
        db.query(KnowledgeSource)
        .filter(
            KnowledgeSource.id == source_id,
            KnowledgeSource.owner_id == trusted_owner_id,
        )
        .first()
    )

    if not source:
        logger.warning(
            "Yêu cầu đọc danh sách chunk thất bại: source_id=%s, owner_id=%s",
            source_id,
            trusted_owner_id,
        )
        raise ChunkNotFoundError("Không tìm thấy tài liệu hoặc bạn không có quyền truy cập")

    chunks = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_id == source_id)
        .order_by(KnowledgeChunk.chunk_index.asc())
        .all()
    )

    return [KnowledgeChunkRead.model_validate(c) for c in chunks]


def build_qdrant_payload(
    db: Session,
    chunk_id: int,
    trusted_owner_id: int,
) -> QdrantChunkPayload:
    """
    Đóng gói payload cho Qdrant Vector Store:
    - Truy vấn Chunk từ PostgreSQL, JOIN KnowledgeSource và xác thực trusted_owner_id.
    - Đảm bảo owner_id trong payload là verified owner từ database, không nhận từ client.
    """
    result = (
        db.query(KnowledgeChunk, KnowledgeSource.owner_id)
        .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
        .filter(
            KnowledgeChunk.id == chunk_id,
            KnowledgeSource.owner_id == trusted_owner_id,
        )
        .first()
    )

    if not result:
        raise ChunkNotFoundError("Không tìm thấy đoạn trích hoặc bạn không có quyền truy cập")

    chunk, verified_owner_id = result

    return QdrantChunkPayload(
        chunk_id=chunk.id,
        source_id=chunk.source_id,
        owner_id=verified_owner_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        page_number=chunk.page_number,
        section=chunk.section,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
    )
