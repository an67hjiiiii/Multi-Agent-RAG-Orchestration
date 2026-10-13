import logging
from pathlib import Path
from typing import Any
import unicodedata

from pypdf import PdfReader
from pypdf.errors import EmptyFileError, FileNotDecryptedError, PyPdfError

from app.core.config import settings
from app.schemas.extraction import ContentSegment

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Ngoại lệ cơ sở cho toàn bộ lỗi trong quá trình trích xuất văn bản."""

    def __init__(self, message: str, code: str = "EXTRACTION_FAILED"):
        super().__init__(message)
        self.message = message
        self.code = code


class EmptyDocumentError(ExtractionError):
    """Tài liệu rỗng hoặc không có dữ liệu để trích xuất."""

    def __init__(self, message: str = "Tài liệu rỗng không có nội dung"):
        super().__init__(message, code="EMPTY_DOCUMENT")


class NoExtractableTextError(ExtractionError):
    """Tài liệu không có lớp văn bản trích xuất được (ví dụ PDF scan ảnh, không có text layer)."""

    def __init__(self, message: str = "Tài liệu không chứa lớp văn bản có thể trích xuất"):
        super().__init__(message, code="NO_EXTRACTABLE_TEXT")


class CorruptedFileError(ExtractionError):
    """Tệp tin bị hỏng cấu trúc hoặc không thể giải mã."""

    def __init__(self, message: str = "Tệp tin bị hỏng cấu trúc không thể giải mã"):
        super().__init__(message, code="CORRUPTED_FILE")


class EncryptedPdfError(ExtractionError):
    """Tệp PDF được bảo vệ bằng mật khẩu hoặc mã hóa không hỗ trợ."""

    def __init__(self, message: str = "Tệp PDF được bảo vệ bằng mật khẩu, không thể xử lý"):
        super().__init__(message, code="ENCRYPTED_PDF")


class ResourceLimitExceededError(ExtractionError):
    """Tài liệu vượt quá giới hạn tài nguyên an toàn (số trang hoặc dung lượng ký tự)."""

    def __init__(self, message: str = "Tài liệu vượt quá giới hạn tài nguyên an toàn"):
        super().__init__(message, code="RESOURCE_LIMIT_EXCEEDED")


class UnsupportedFormatError(ExtractionError):
    """Định dạng tệp không được hỗ trợ trích xuất."""

    def __init__(self, message: str = "Định dạng tệp không được hỗ trợ"):
        super().__init__(message, code="UNSUPPORTED_FORMAT")


def normalize_text(text: str, preserve_markdown: bool = False) -> str:
    """
    Chuẩn hóa văn bản an toàn bảo toàn ý nghĩa kỹ thuật:
    - Kiểm tra null bytes (từ chối tệp nhị phân giả mạo).
    - Chuẩn hóa Unicode NFC (giữ trọn vẹn tiếng Việt dựng sẵn và tổ hợp).
    - Thống nhất ký tự ngắt dòng về \\n.
    - Bảo toàn tabs, indentation, markdown headings (#), code fences (```), và ký hiệu code.
    - Không âm thầm xóa ký tự lỗi.
    """
    if "\x00" in text:
        raise CorruptedFileError("Văn bản chứa ký tự null không hợp lệ")

    # 1. Chuẩn hóa Unicode NFC (an toàn cho tiếng Việt)
    normalized = unicodedata.normalize("NFC", text)

    # 2. Thống nhất ký tự xuống dòng về \n
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    return normalized


def extract_txt(file_path: Path) -> tuple[str, list[ContentSegment], dict[str, Any]]:
    """
    Trích xuất văn bản từ tệp TXT UTF-8 thuần túy.
    """
    try:
        raw_bytes = file_path.read_bytes()
    except OSError as e:
        logger.warning("Không thể đọc tệp TXT từ đĩa: %s", type(e).__name__)
        raise CorruptedFileError("Không thể đọc tệp văn bản từ đĩa")

    if len(raw_bytes) == 0:
        raise EmptyDocumentError("Tệp văn bản rỗng (0 bytes)")

    try:
        raw_text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise CorruptedFileError("Tệp văn bản chứa mã hóa UTF-8 không hợp lệ")

    normalized_text = normalize_text(raw_text, preserve_markdown=False)

    if not normalized_text.strip():
        raise NoExtractableTextError("Tệp văn bản không chứa nội dung chữ có nghĩa")

    segment = ContentSegment(
        segment_index=1,
        text=normalized_text,
        char_count=len(normalized_text),
        page_number=None,
    )

    metadata = {
        "format": "txt",
        "segment_count": 1,
    }

    return normalized_text, [segment], metadata


def extract_markdown(file_path: Path) -> tuple[str, list[ContentSegment], dict[str, Any]]:
    """
    Trích xuất văn bản từ tệp Markdown UTF-8, bảo toàn toàn bộ headings,
    fenced code blocks, bảng biểu, danh sách và indentation.
    """
    try:
        raw_bytes = file_path.read_bytes()
    except OSError as e:
        logger.warning("Không thể đọc tệp Markdown từ đĩa: %s", type(e).__name__)
        raise CorruptedFileError("Không thể đọc tệp Markdown từ đĩa")

    if len(raw_bytes) == 0:
        raise EmptyDocumentError("Tệp Markdown rỗng (0 bytes)")

    try:
        raw_text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise CorruptedFileError("Tệp Markdown chứa mã hóa UTF-8 không hợp lệ")

    normalized_text = normalize_text(raw_text, preserve_markdown=True)

    if not normalized_text.strip():
        raise NoExtractableTextError("Tệp Markdown không chứa nội dung chữ có nghĩa")

    segment = ContentSegment(
        segment_index=1,
        text=normalized_text,
        char_count=len(normalized_text),
        page_number=None,
    )

    metadata = {
        "format": "markdown",
        "segment_count": 1,
        "has_headings": "#" in normalized_text,
        "has_code_blocks": "```" in normalized_text,
    }

    return normalized_text, [segment], metadata


def extract_pdf(
    file_path: Path,
    max_pages: int | None = None,
    max_chars: int | None = None,
) -> tuple[str, list[ContentSegment], dict[str, Any]]:
    """
    Trích xuất văn bản từ tệp PDF:
    - Sử dụng pypdf đọc text layer từng trang.
    - Giữ trọn vẹn số trang gốc (page_number >= 1) và thứ tự trang trong provenance.
    - Kiểm tra bảo vệ mật khẩu / mã hóa (is_encrypted).
    - Kiểm tra giới hạn an toàn tài nguyên (số trang và tổng số ký tự).
    - Xử lý PDF hỏng cấu trúc, PDF scan không có text layer.
    """
    if max_pages is None:
        max_pages = settings.max_pdf_pages
    if max_chars is None:
        max_chars = settings.max_extracted_chars

    try:
        file_size = file_path.stat().st_size
    except OSError as e:
        logger.warning("Không thể kiểm tra kích thước tệp PDF: %s", type(e).__name__)
        raise CorruptedFileError("Không thể đọc tệp PDF từ đĩa")

    if file_size == 0:
        raise EmptyDocumentError("Tệp PDF rỗng (0 bytes)")

    try:
        reader = PdfReader(str(file_path))
    except (EmptyFileError, ValueError) as e:
        logger.warning("Tệp PDF không hợp lệ hoặc rỗng: %s", type(e).__name__)
        raise EmptyDocumentError("Tệp PDF rỗng hoặc không có dữ liệu hợp lệ")
    except PyPdfError as e:
        logger.warning("Lỗi khi mở cấu trúc PDF: %s", type(e).__name__)
        raise CorruptedFileError("Tệp PDF bị hỏng cấu trúc không thể giải mã")
    except Exception as e:
        logger.warning("Ngoại lệ bất ngờ khi đọc PDF: %s", type(e).__name__)
        raise CorruptedFileError("Không thể giải mã cấu trúc tệp PDF")

    if reader.is_encrypted:
        raise EncryptedPdfError("Tệp PDF được bảo vệ bằng mật khẩu hoặc mã hóa không hỗ trợ")

    try:
        total_pages = len(reader.pages)
    except Exception as e:
        logger.warning("Không thể đọc danh sách trang PDF: %s", type(e).__name__)
        raise CorruptedFileError("Cấu trúc bảng trang của PDF bị hỏng")

    if total_pages == 0:
        raise EmptyDocumentError("Tệp PDF không chứa trang nào")

    if total_pages > max_pages:
        raise ResourceLimitExceededError(
            f"Tài liệu PDF vượt quá giới hạn tối đa cho phép ({total_pages} trang > {max_pages} trang)"
        )

    segments: list[ContentSegment] = []
    accumulated_texts: list[str] = []
    total_chars = 0
    pages_with_text = 0

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        try:
            raw_page_text = page.extract_text() or ""
        except Exception as e:
            logger.warning("Lỗi trích xuất trang %d: %s", page_num, type(e).__name__)
            # Theo Master Contract: Nếu một trang bị lỗi parser khiến không thể xác nhận kết quả đầy đủ,
            # không trả phần còn lại như SUCCESS.
            raise CorruptedFileError(f"Lỗi khi trích xuất nội dung văn bản tại trang {page_num}")

        norm_page_text = normalize_text(raw_page_text, preserve_markdown=False)

        if norm_page_text.strip():
            pages_with_text += 1

        page_char_count = len(norm_page_text)
        total_chars += page_char_count

        if total_chars > max_chars:
            raise ResourceLimitExceededError(
                f"Dung lượng văn bản trích xuất vượt quá giới hạn an toàn ({total_chars} ký tự > {max_chars} ký tự)"
            )

        segment = ContentSegment(
            segment_index=page_num,
            text=norm_page_text,
            char_count=page_char_count,
            page_number=page_num,
        )
        segments.append(segment)
        accumulated_texts.append(norm_page_text)

    # Ghép văn bản tổng thể giữa các trang phân tách bằng dấu ngắt dòng đôi
    full_text = "\n\n".join(accumulated_texts)

    if pages_with_text == 0 or not full_text.strip():
        raise NoExtractableTextError(
            "Tệp PDF không chứa lớp văn bản có thể trích xuất (tài liệu rỗng hoặc là ảnh quét)"
        )

    metadata = {
        "format": "pdf",
        "total_pages": total_pages,
        "pages_with_text": pages_with_text,
    }

    return full_text, segments, metadata


def extract_document(
    file_path: Path,
    ext: str,
    max_pages: int | None = None,
    max_chars: int | None = None,
) -> tuple[str, list[ContentSegment], dict[str, Any]]:
    """
    Dispatcher trích xuất theo phần mở rộng tệp (.txt, .md, .pdf).
    """
    clean_ext = ext.lower().strip()
    if clean_ext == ".txt":
        return extract_txt(file_path)
    elif clean_ext == ".md":
        return extract_markdown(file_path)
    elif clean_ext == ".pdf":
        return extract_pdf(file_path, max_pages=max_pages, max_chars=max_chars)
    else:
        raise UnsupportedFormatError(f"Định dạng tệp không được hỗ trợ: {ext}")
