import codecs
from datetime import datetime
import logging
import os
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import lay_nguoi_dung_hien_tai
from app.core.config import settings
from app.db.database import get_db
from app.models.knowledge import KnowledgeSource
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

CHUNK_SIZE = 64 * 1024  # 64 KiB


class PhanHoiUpload(BaseModel):
    id: int
    filename: str
    file_size: int
    mime_type: str
    status: str
    created_at: datetime


def _chuan_hoa_ten_file(raw_filename: str | None) -> str:
    if not raw_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên tập tin không được để trống",
        )

    ten_chuan = os.path.basename(raw_filename.replace("\\", "/")).strip()
    if not ten_chuan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên tập tin không hợp lệ",
        )

    if len(ten_chuan) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên tập tin không được vượt quá 255 ký tự",
        )

    if any(ord(c) < 32 for c in ten_chuan):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên tập tin chứa ký tự điều khiển không hợp lệ",
        )

    return ten_chuan


def _xoa_file_an_toan(duong_dan_file: Path) -> None:
    try:
        if duong_dan_file.exists():
            duong_dan_file.unlink()
    except OSError as err:
        logger.warning(
            "Không thể dọn dẹp tệp tạm %s: %s",
            duong_dan_file.name,
            err,
        )


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=PhanHoiUpload,
)
def tai_len_tai_lieu(
    file: UploadFile = File(...),
    current_user: User = Depends(lay_nguoi_dung_hien_tai),
    db: Session = Depends(get_db),
):
    original_filename = _chuan_hoa_ten_file(file.filename)
    ext = Path(original_filename).suffix.lower()

    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng tập tin không được hỗ trợ",
        )

    if ext == ".pdf":
        mime_type = "application/pdf"
    elif ext == ".md":
        mime_type = "text/markdown"
    else:
        mime_type = "text/plain"

    try:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi chuẩn bị thư mục lưu trữ",
        )

    file_disk_name = f"{uuid4().hex}{ext}"
    target_file_path = settings.upload_dir / file_disk_name
    stored_path = f"uploads/{file_disk_name}"

    total_bytes = 0
    file_created_on_disk = False
    commit_success = False
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict") if ext in (".txt", ".md") else None

    try:
        try:
            first_chunk = file.file.read(CHUNK_SIZE)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lỗi khi đọc dữ liệu tập tin tải lên",
            )

        if not first_chunk or len(first_chunk) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tập tin rỗng không hợp lệ",
            )

        if ext == ".pdf" and not first_chunk.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tập tin PDF không hợp lệ",
            )

        if ext in (".txt", ".md"):
            if b"\x00" in first_chunk:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tập tin văn bản chứa ký tự không hợp lệ",
                )
            try:
                decoder.decode(first_chunk, final=False)
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tập tin văn bản phải có định dạng mã hóa UTF-8 hợp lệ",
                )

        try:
            with open(target_file_path, "xb") as f:
                file_created_on_disk = True
                f.write(first_chunk)
                total_bytes += len(first_chunk)

                if total_bytes > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Dung lượng tập tin vượt quá giới hạn 10MB",
                    )

                while True:
                    chunk = file.file.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    total_bytes += len(chunk)
                    if total_bytes > settings.max_upload_size_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail="Dung lượng tập tin vượt quá giới hạn 10MB",
                        )

                    if ext in (".txt", ".md"):
                        if b"\x00" in chunk:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Tập tin văn bản chứa ký tự không hợp lệ",
                            )
                        try:
                            decoder.decode(chunk, final=False)
                        except UnicodeDecodeError:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Tập tin văn bản phải có định dạng mã hóa UTF-8 hợp lệ",
                            )

                    f.write(chunk)
        except FileExistsError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi hệ thống khi khởi tạo tập tin lưu trữ",
            )
        except OSError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi hệ thống khi lưu trữ tập tin",
            )

        if ext in (".txt", ".md") and decoder is not None:
            try:
                decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tập tin văn bản phải có định dạng mã hóa UTF-8 hợp lệ",
                )

        ban_ghi = KnowledgeSource(
            owner_id=current_user.id,
            original_filename=original_filename,
            stored_path=stored_path,
            file_size=total_bytes,
            mime_type=mime_type,
            status="UPLOADED",
        )

        try:
            db.add(ban_ghi)
            db.flush()

            response_data = PhanHoiUpload(
                id=ban_ghi.id,
                filename=ban_ghi.original_filename,
                file_size=ban_ghi.file_size,
                mime_type=ban_ghi.mime_type,
                status=ban_ghi.status,
                created_at=ban_ghi.created_at,
            )

            db.commit()
            commit_success = True
        except SQLAlchemyError as db_err:
            logger.warning("Lỗi cơ sở dữ liệu khi lưu metadata: %s", type(db_err).__name__)
            try:
                db.rollback()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi hệ thống khi lưu thông tin tài liệu",
            )
        except Exception as inner_err:
            logger.exception("Lỗi bất thường sau khi flush bản ghi: %s", type(inner_err).__name__)
            try:
                db.rollback()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi hệ thống bất ngờ khi xử lý tập tin",
            )

    except HTTPException:
        if not commit_success:
            try:
                db.rollback()
            except Exception:
                pass
            if file_created_on_disk:
                _xoa_file_an_toan(target_file_path)
        raise
    except Exception as exc:
        logger.exception("Lỗi bất thường trong quá trình tải lên: %s", type(exc).__name__)
        if not commit_success:
            try:
                db.rollback()
            except Exception:
                pass
            if file_created_on_disk:
                _xoa_file_an_toan(target_file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống bất ngờ khi xử lý tập tin",
        )
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    return response_data
