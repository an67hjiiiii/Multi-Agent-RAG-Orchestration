from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import bam_mat_khau
from app.db.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class YeuCauDangKy(BaseModel):
    email: EmailStr
    name: str
    password: str


class PhanHoiDangKy(BaseModel):
    id: int
    email: str
    name: str
    message: str


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=PhanHoiDangKy,
)
def dang_ky_nguoi_dung(
    payload: YeuCauDangKy,
    db: Session = Depends(get_db),
):
    if not payload.name or payload.name.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Họ tên không được để trống",
        )

    ten_chuan_hoa = payload.name.strip()
    if len(ten_chuan_hoa) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Họ tên không được vượt quá 100 ký tự",
        )

    if not payload.password or payload.password.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu không được để trống",
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải có ít nhất 8 ký tự",
        )

    email_chuan_hoa = str(payload.email).strip().lower()

    try:
        nguoi_dung_cu = db.scalar(
            select(User).where(User.email == email_chuan_hoa)
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi đăng ký người dùng",
        )

    if nguoi_dung_cu is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký",
        )

    mat_khau_da_bam = bam_mat_khau(payload.password)

    nguoi_dung_moi = User(
        email=email_chuan_hoa,
        name=ten_chuan_hoa,
        password_hash=mat_khau_da_bam,
        role="USER",
    )

    try:
        db.add(nguoi_dung_moi)
        db.flush()
        id_nguoi_dung = nguoi_dung_moi.id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi đăng ký người dùng",
        )

    return PhanHoiDangKy(
        id=id_nguoi_dung,
        email=email_chuan_hoa,
        name=ten_chuan_hoa,
        message="Đăng ký thành công",
    )