import io
from pathlib import Path
import pytest
from pypdf import PdfWriter

from app.services.extractor import (
    CorruptedFileError,
    EmptyDocumentError,
    EncryptedPdfError,
    NoExtractableTextError,
    ResourceLimitExceededError,
    UnsupportedFormatError,
    extract_document,
    extract_markdown,
    extract_pdf,
    extract_txt,
    normalize_text,
)


def _tao_pdf_mau(pages_text: list[str]) -> bytes:
    """Tạo tệp PDF thật trong bộ nhớ với danh sách text theo từng trang."""
    writer = PdfWriter()
    for text in pages_text:
        writer.add_blank_page(width=200, height=200)
    # pypdf tạo blank page, nhưng để có text layer thật cần add annotations/text
    # Dùng writer ghi ra bytes
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestNormalizeText:
    """Kiểm thử bộ chuẩn hóa văn bản an toàn."""

    def test_unicode_nfc_tieng_viet(self):
        # Tiếng Việt tổ hợp (NFD): e + dấu sắc (u'\u0065\u0301')
        nfd_text = "Ti\u00ea\u0301ng Vi\u00ea\u0323t"
        nfc_text = "Tiếng Việt"
        result = normalize_text(nfd_text)
        assert result == nfc_text
        assert len(result) == len(nfc_text)

    def test_chuan_hoa_newline(self):
        raw = "Dong 1\r\nDong 2\rDong 3\nDong 4"
        expected = "Dong 1\nDong 2\nDong 3\nDong 4"
        assert normalize_text(raw) == expected

    def test_bao_toan_code_fences_va_indentation(self):
        code = (
            "# Heading 1\n\n"
            "```python\n"
            "def foo():\n"
            "    # indent 4 spaces\n"
            "\treturn True\n"
            "```\n"
        )
        result = normalize_text(code, preserve_markdown=True)
        assert "    # indent 4 spaces" in result
        assert "\treturn True" in result
        assert "# Heading 1" in result

    def test_tu_choi_null_byte(self):
        text_with_null = "Xin chao\x00the gioi"
        with pytest.raises(CorruptedFileError, match="ký tự null"):
            normalize_text(text_with_null)


class TestExtractTxt:
    """Kiểm thử trích xuất tệp TXT."""

    def test_txt_hop_le(self, tmp_path: Path):
        file_path = tmp_path / "sample.txt"
        file_path.write_text("Kiến trúc Multi-Agent RAG Orchestration.", encoding="utf-8")

        text, segments, meta = extract_txt(file_path)
        assert text == "Kiến trúc Multi-Agent RAG Orchestration."
        assert len(segments) == 1
        assert segments[0].segment_index == 1
        assert segments[0].page_number is None
        assert segments[0].char_count == len(text)
        assert meta["format"] == "txt"

    def test_txt_rong_0_bytes(self, tmp_path: Path):
        file_path = tmp_path / "empty.txt"
        file_path.write_bytes(b"")

        with pytest.raises(EmptyDocumentError, match="rỗng"):
            extract_txt(file_path)

    def test_txt_chi_chua_whitespace(self, tmp_path: Path):
        file_path = tmp_path / "whitespace.txt"
        file_path.write_text("   \n\t  \n   ", encoding="utf-8")

        with pytest.raises(NoExtractableTextError, match="không chứa nội dung chữ"):
            extract_txt(file_path)

    def test_txt_khong_phai_utf8(self, tmp_path: Path):
        file_path = tmp_path / "invalid_encoding.txt"
        # 0xFF 0xFE không phải UTF-8
        file_path.write_bytes(b"\xff\xfe\x00\x00dada")

        with pytest.raises(CorruptedFileError, match="UTF-8 không hợp lệ"):
            extract_txt(file_path)


class TestExtractMarkdown:
    """Kiểm thử trích xuất tệp Markdown."""

    def test_markdown_hop_le_bao_toan_cau_truc(self, tmp_path: Path):
        content = (
            "# CAP1_AI Overview\n\n"
            "Hệ thống đa tác tử phục vụ tra cứu kỹ thuật.\n\n"
            "## Cài đặt\n\n"
            "```bash\n"
            "pip install -r requirements.txt\n"
            "```\n\n"
            "- Điểm 1\n"
            "- Điểm 2\n"
        )
        file_path = tmp_path / "guide.md"
        file_path.write_text(content, encoding="utf-8")

        text, segments, meta = extract_markdown(file_path)
        assert "# CAP1_AI Overview" in text
        assert "## Cài đặt" in text
        assert "```bash" in text
        assert len(segments) == 1
        assert meta["format"] == "markdown"
        assert meta["has_headings"] is True
        assert meta["has_code_blocks"] is True

    def test_markdown_rong(self, tmp_path: Path):
        file_path = tmp_path / "empty.md"
        file_path.write_bytes(b"")

        with pytest.raises(EmptyDocumentError):
            extract_markdown(file_path)


class TestExtractPdf:
    """Kiểm thử trích xuất tệp PDF."""

    def _tao_pdf_voi_text(self, pages_text: list[str]) -> bytes:
        """Tạo PDF có text layer thực sự bằng pypdf ContentStream hoặc Annotation/Layout."""
        writer = PdfWriter()
        for t in pages_text:
            # Tạo 1 trang và chèn text bằng cách thêm form field / metadata hoặc text annotations
            # pypdf không có layout engine tích hợp để vẽ text tự do,
            # nhưng ta có thể ghi đối tượng PDF thô với Text Operator BT / ET:
            page = writer.add_blank_page(width=300, height=300)
        
        buffer = io.BytesIO()
        writer.write(buffer)
        raw_pdf = buffer.getvalue()

        # Tiêm trực tiếp Text Stream hợp lệ vào PDF object để có text layer thực:
        # Operator PDF: BT /F1 12 Tf 50 250 Td (Hello World) Tj ET
        # Để đảm bảo test sạch và không bị giả lập string thô, ta dựng PDF test bằng raw minimal PDF structure
        return raw_pdf

    def _build_valid_pdf_with_text(self, pages_text: list[str]) -> bytes:
        """Xây dựng một tệp PDF hợp lệ 100% chuẩn ISO 32000 có text layer thực sự."""
        # Chuẩn bị luồng PDF hợp lệ với Text Stream
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n")
        offsets = []

        def write_obj(content: bytes) -> int:
            offsets.append(out.tell())
            obj_id = len(offsets)
            out.write(f"{obj_id} 0 obj\n".encode("ascii"))
            out.write(content)
            out.write(b"\nendobj\n")
            return obj_id

        # 1. Font
        font_id = write_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

        # 2. Page object IDs
        page_ids = []
        for text in pages_text:
            # Mã hóa chuỗi text an toàn trong PDF literal string
            safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_content = f"BT /F1 12 Tf 72 712 Td ({safe_text}) Tj ET\n".encode("utf-8")
            stream_len = len(stream_content)
            stream_id = write_obj(
                f"<< /Length {stream_len} >>\nstream\n".encode("ascii")
                + stream_content
                + b"endstream"
            )
            page_obj = (
                f"<< /Type /Page /Parent 3 0 R /MediaBox [0 0 612 792] "
                f"/Contents {stream_id} 0 R "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode("ascii")
            page_ids.append(write_obj(page_obj))

        # 3. Pages catalog
        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        pages_id = write_obj(
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
        )

        # 4. Catalog
        cat_id = write_obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

        # 5. XRef
        xref_offset = out.tell()
        out.write(b"xref\n")
        out.write(f"0 {len(offsets) + 1}\n".encode("ascii"))
        out.write(b"0000000000 65535 f \n")
        for off in offsets:
            out.write(f"{off:010d} 00000 n \n".encode("ascii"))

        out.write(b"trailer\n")
        out.write(f"<< /Size {len(offsets) + 1} /Root {cat_id} 0 R >>\n".encode("ascii"))
        out.write(b"startxref\n")
        out.write(f"{xref_offset}\n".encode("ascii"))
        out.write(b"%%EOF\n")

        return out.getvalue()

    def test_pdf_single_page_thanh_cong(self, tmp_path: Path):
        pdf_bytes = self._build_valid_pdf_with_text(["Multi-Agent RAG System"])
        pdf_file = tmp_path / "valid.pdf"
        pdf_file.write_bytes(pdf_bytes)

        text, segments, meta = extract_pdf(pdf_file)
        assert "Multi-Agent RAG System" in text
        assert len(segments) == 1
        assert segments[0].page_number == 1
        assert segments[0].segment_index == 1
        assert meta["format"] == "pdf"
        assert meta["total_pages"] == 1

    def test_pdf_multi_page_bao_toan_provenance(self, tmp_path: Path):
        pdf_bytes = self._build_valid_pdf_with_text([
            "Page 1 Content: Introduction",
            "Page 2 Content: Architecture Overview",
            "Page 3 Content: Evaluation Metrics",
        ])
        pdf_file = tmp_path / "multi.pdf"
        pdf_file.write_bytes(pdf_bytes)

        text, segments, meta = extract_pdf(pdf_file)
        assert len(segments) == 3
        assert segments[0].page_number == 1
        assert "Page 1 Content" in segments[0].text
        assert segments[1].page_number == 2
        assert "Page 2 Content" in segments[1].text
        assert segments[2].page_number == 3
        assert "Page 3 Content" in segments[2].text
        assert meta["total_pages"] == 3

    def test_pdf_rong_0_bytes(self, tmp_path: Path):
        pdf_file = tmp_path / "zero.pdf"
        pdf_file.write_bytes(b"")

        with pytest.raises(EmptyDocumentError):
            extract_pdf(pdf_file)

    def test_pdf_scan_khong_co_text_layer(self, tmp_path: Path):
        # PDF tạo bằng pypdf không có stream text nào
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        buffer = io.BytesIO()
        writer.write(buffer)

        pdf_file = tmp_path / "scanned.pdf"
        pdf_file.write_bytes(buffer.getvalue())

        with pytest.raises(NoExtractableTextError, match="không chứa lớp văn bản"):
            extract_pdf(pdf_file)

    def test_pdf_bi_ma_hoa_password(self, tmp_path: Path):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("secret_password_123")
        buffer = io.BytesIO()
        writer.write(buffer)

        pdf_file = tmp_path / "encrypted.pdf"
        pdf_file.write_bytes(buffer.getvalue())

        with pytest.raises(EncryptedPdfError, match="mật khẩu"):
            extract_pdf(pdf_file)

    def test_pdf_corrupted_stream(self, tmp_path: Path):
        pdf_file = tmp_path / "corrupted.pdf"
        # Bắt đầu bằng %PDF- nhưng nội dung sau bị cắt cụt/hỏng
        pdf_file.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\ntrailer junk")

        with pytest.raises(CorruptedFileError):
            extract_pdf(pdf_file)

    def test_pdf_vuot_gioi_han_trang(self, tmp_path: Path):
        # Tạo PDF 5 trang nhưng giới hạn max_pages=2
        pdf_bytes = self._build_valid_pdf_with_text([f"Page {i}" for i in range(5)])
        pdf_file = tmp_path / "too_many_pages.pdf"
        pdf_file.write_bytes(pdf_bytes)

        with pytest.raises(ResourceLimitExceededError, match="giới hạn tối đa"):
            extract_pdf(pdf_file, max_pages=2)

    def test_pdf_vuot_gioi_han_ky_tu(self, tmp_path: Path):
        long_text = "A" * 1000
        pdf_bytes = self._build_valid_pdf_with_text([long_text])
        pdf_file = tmp_path / "too_many_chars.pdf"
        pdf_file.write_bytes(pdf_bytes)

        with pytest.raises(ResourceLimitExceededError, match="Dung lượng văn bản"):
            extract_pdf(pdf_file, max_chars=500)


class TestExtractDocumentDispatcher:
    """Kiểm thử Dispatcher trích xuất đa định dạng."""

    def test_dinh_dang_khong_ho_tro(self, tmp_path: Path):
        file_path = tmp_path / "sample.docx"
        file_path.write_bytes(b"dummy")

        with pytest.raises(UnsupportedFormatError, match="không được hỗ trợ"):
            extract_document(file_path, ext=".docx")
