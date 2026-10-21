import logging
from pathlib import Path
import re
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeSource
from app.schemas.extraction import StructuredExtractionResult
from app.services.extractor import (
    ExtractionError,
    extract_document,
)

logger = logging.getLogger(__name__)

# Pattern kiểm tra stored_path theo contract thực tế của Sprint 1:
# stored_path = "uploads/<uuid4_hex><supported_ext>"
_STORED_PATH_PATTERN = re.compile(r"^uploads/[a-f0-9]{32}\.(txt|md|pdf)$", re.IGNORECASE)


class IngestionError(Exception):
    """Lỗi xử lý trong quy trình nạp tài liệu."""

    def __init__(self, message: str, code: str = "INGESTION_FAILED"):
        super().__init__(message)
        self.message = message
        self.code = code


class IngestionNotFoundError(IngestionError):
    """Không tìm thấy tài liệu hoặc không có quyền sở hữu."""

    def __init__(self, message: str = "Không tìm thấy tài liệu hoặc bạn không có quyền truy cập"):
        super().__init__(message, code="NOT_FOUND")


class IngestionSecurityError(IngestionError):
    """Vi phạm an toàn hệ thống tệp hoặc ranh giới lưu trữ."""

    def __init__(self, message: str = "Đường dẫn lưu trữ tài liệu không an toàn"):
        super().__init__(message, code="SECURITY_VIOLATION")


class IngestionDatabaseError(IngestionError):
    """Lỗi khi lưu trữ hoặc cập nhật trạng thái vào cơ sở dữ liệu."""

    def __init__(self, message: str = "Lỗi cơ sở dữ liệu khi cập nhật trạng thái tài liệu", code: str = "DB_PERSISTENCE_FAILED"):
        super().__init__(message, code=code)


class IngestionLifecycleError(IngestionError):
    """Trạng thái hiện tại của tài liệu không cho phép trích xuất."""

    def __init__(self, message: str = "Trạng thái tài liệu không hợp lệ để trích xuất", code: str = "INVALID_STATE"):
        super().__init__(message, code=code)


def _resolve_and_verify_storage_path(stored_path: str) -> Path:
    """
    Xác minh và phân giải đường dẫn lưu trữ tệp tin theo tiêu chuẩn bảo mật nghiêm ngặt:
    1. Kiểm tra contract định dạng: 'uploads/<uuid>.<ext>'
    2. Chống Path Traversal (từ chối .., \\, symlink nguy hiểm)
    3. Phân giải tương đối với settings.upload_dir
    4. Kiểm tra containment bên trong upload_dir.resolve()
    5. Kiểm tra tệp tồn tại và là regular file (is_file)
    """
    if not stored_path or not _STORED_PATH_PATTERN.match(stored_path):
        logger.warning("Cấu trúc stored_path không khớp contract an toàn")
        raise IngestionSecurityError("Cấu trúc đường dẫn tệp không hợp lệ")

    filename = Path(stored_path).name
    upload_root = settings.upload_dir.resolve()
    target_path = (upload_root / filename).resolve()

    # Kiểm tra không được là symlink (ngăn chặn symlink trỏ ra ngoài upload root)
    if (upload_root / filename).is_symlink() or target_path.is_symlink():
        logger.warning("Phát hiện liên kết symlink không được phép")
        raise IngestionSecurityError("Liên kết symlink không được phép trên hệ thống lưu trữ")

    # Kiểm tra containment
    try:
        if not target_path.is_relative_to(upload_root):
            logger.warning("Phát hiện đường dẫn vượt ra ngoài upload_dir")
            raise IngestionSecurityError("Đường dẫn tệp nằm ngoài vùng lưu trữ cho phép")
    except AttributeError:
        # Hỗ trợ nếu trên phiên bản python cũ
        if not str(target_path).startswith(str(upload_root)):
            raise IngestionSecurityError("Đường dẫn tệp nằm ngoài vùng lưu trữ cho phép")

    if not target_path.exists() or not target_path.is_file():
        logger.warning("Tệp tin không tồn tại trên hệ thống lưu trữ")
        raise IngestionSecurityError("Tệp tin vật lý không tồn tại trên hệ thống")

    return target_path


def process_knowledge_source(
    db: Session,
    source_id: int,
    trusted_owner_id: int,
) -> StructuredExtractionResult:
    """
    Thực hiện quy trình trích xuất văn bản từ KnowledgeSource:
    1. Xác minh quyền sở hữu và truy vấn KnowledgeSource bằng id + trusted_owner_id.
    2. Nếu không tìm thấy hoặc sai owner: ném IngestionNotFoundError (chống IDOR).
    3. Kiểm tra vòng đời trạng thái:
       - CẤM chạy lại nếu source đang ở trạng thái READY (tránh hạ trạng thái READY).
       - Cho phép chạy khi UPLOADED, FAILED, hoặc EXTRACTED (re-extract).
    4. Kiểm tra và phân giải đường dẫn lưu trữ vật lý an toàn.
    5. Gọi Dispatcher trích xuất văn bản tương ứng (.txt, .md, .pdf).
    6. Đóng gói StructuredExtractionResult DTO.
    7. Chuyển trạng thái và xử lý lỗi DB chính xác:
       - Thành công trích xuất: commit status = "EXTRACTED". Nếu commit lỗi -> ném IngestionDatabaseError("EXTRACTION_SUCCESS_DB_FAILED").
       - Lỗi trích xuất: rollback DB, gán status = "FAILED".
         + Nếu commit FAILED thành công -> ném IngestionError (FAILED persisted).
         + Nếu commit FAILED thất bại -> ném IngestionDatabaseError("EXTRACTION_FAILED_DB_FAILED").
    """
    # 1. Truy vấn source gắn chặt với trusted_owner_id
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
            "Yêu cầu xử lý tài liệu không hợp lệ: source_id=%s, owner_id=%s",
            source_id,
            trusted_owner_id,
        )
        raise IngestionNotFoundError("Không tìm thấy tài liệu hoặc bạn không có quyền truy cập")

    # 2. Kiểm tra vòng đời trạng thái tài liệu
    if source.status == "READY":
        logger.warning(
            "Từ chối trích xuất lại tài liệu đã READY: source_id=%s",
            source_id,
        )
        raise IngestionLifecycleError(
            "Tài liệu đã ở trạng thái READY hoàn chỉnh, không được phép trích xuất lại làm thay đổi trạng thái"
        )

    # 3. Xác minh và phân giải đường dẫn tệp vật lý
    try:
        resolved_file_path = _resolve_and_verify_storage_path(source.stored_path)
    except IngestionSecurityError as sec_err:
        # Cập nhật trạng thái FAILED cho source của chính owner này
        try:
            source.status = "FAILED"
            db.commit()
        except Exception:
            db.rollback()
            raise IngestionDatabaseError(
                "Đường dẫn tệp không an toàn và không thể ghi nhận trạng thái lỗi vào cơ sở dữ liệu",
                code="SECURITY_FAILED_DB_FAILED",
            )
        raise sec_err

    # 4. Tiến hành trích xuất văn bản
    file_ext = resolved_file_path.suffix.lower()
    try:
        extracted_text, segments, metadata = extract_document(
            file_path=resolved_file_path,
            ext=file_ext,
            max_pages=settings.max_pdf_pages,
            max_chars=settings.max_extracted_chars,
        )

        # 5. Đóng gói DTO kết quả
        result = StructuredExtractionResult(
            source_id=source.id,
            owner_id=source.owner_id,
            original_filename=source.original_filename,
            mime_type=source.mime_type,
            text=extracted_text,
            char_count=len(extracted_text),
            segments=segments,
            metadata=metadata,
        )

        # 6. Cập nhật trạng thái thành công EXTRACTED
        source.status = "EXTRACTED"
        try:
            db.commit()
            db.refresh(source)
        except Exception as db_err:
            logger.warning("Lỗi DB khi commit trạng thái EXTRACTED: %s", type(db_err).__name__)
            db.rollback()
            raise IngestionDatabaseError(
                "Trích xuất văn bản thành công nhưng không thể lưu trạng thái vào cơ sở dữ liệu",
                code="EXTRACTION_SUCCESS_DB_FAILED",
            )

        return result

    except ExtractionError as extract_err:
        logger.warning(
            "Lỗi trích xuất tài liệu source_id=%s, code=%s",
            source.id,
            extract_err.code,
        )
        # Rollback giao dịch trước khi cập nhật FAILED
        db.rollback()
        failed_persisted = False
        try:
            source.status = "FAILED"
            db.commit()
            failed_persisted = True
        except Exception as commit_failed_err:
            logger.warning(
                "Không thể commit trạng thái FAILED cho source_id=%s: %s",
                source.id,
                type(commit_failed_err).__name__,
            )
            db.rollback()

        if not failed_persisted:
            raise IngestionDatabaseError(
                "Trích xuất tài liệu thất bại và không thể ghi nhận trạng thái FAILED vào cơ sở dữ liệu",
                code="EXTRACTION_FAILED_DB_FAILED",
            )

        raise IngestionError(extract_err.message, code=extract_err.code)

    except IngestionDatabaseError:
        raise

    except Exception as exc:
        logger.warning(
            "Lỗi không mong muốn trong quá trình trích xuất source_id=%s: %s",
            source.id,
            type(exc).__name__,
        )
        db.rollback()
        failed_persisted = False
        try:
            source.status = "FAILED"
            db.commit()
            failed_persisted = True
        except Exception:
            db.rollback()

        if not failed_persisted:
            raise IngestionDatabaseError(
                "Lỗi bất ngờ khi trích xuất và không thể lưu trạng thái lỗi vào cơ sở dữ liệu",
                code="INTERNAL_ERROR_DB_FAILED",
            )

        raise IngestionError("Lỗi hệ thống bất ngờ khi trích xuất tài liệu", code="INTERNAL_ERROR")
