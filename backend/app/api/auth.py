from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    bam_ma_phien,
    bam_mat_khau,
    tao_ma_phien,
    xac_thuc_mat_khau,
)
from app.db.database import get_db
from app.models.session import PhienDangNhap
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


class ThongTinNguoiDung(BaseModel):
    id: int
    email: str
    name: str | None
    role: str


class YeuCauDangNhap(BaseModel):
    email: EmailStr
    password: str


class PhanHoiDangNhap(BaseModel):
    authenticated: bool
    user: ThongTinNguoiDung


class PhanHoiPhien(BaseModel):
    authenticated: bool
    user: ThongTinNguoiDung | None


class PhanHoiDangXuat(BaseModel):
    ok: bool
    authenticated: bool


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


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=PhanHoiDangNhap,
)
def dang_nhap(
    payload: YeuCauDangNhap,
    response: Response,
    db: Session = Depends(get_db),
):
    email_chuan_hoa = str(payload.email).strip().lower()

    try:
        nguoi_dung = db.scalar(
            select(User).where(User.email == email_chuan_hoa)
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi đăng nhập",
        )

    if nguoi_dung is None or not xac_thuc_mat_khau(
        payload.password, nguoi_dung.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    ma_phien_goc = tao_ma_phien()
    ma_bam = bam_ma_phien(ma_phien_goc)
    thoi_diem_hien_tai = datetime.now(timezone.utc)
    thoi_diem_het_han = thoi_diem_hien_tai + timedelta(
        minutes=settings.thoi_han_phien_phut
    )

    phien_moi = PhienDangNhap(
        ma_nguoi_dung=nguoi_dung.id,
        ma_bam_phien=ma_bam,
        thoi_gian_tao=thoi_diem_hien_tai,
        thoi_gian_het_han=thoi_diem_het_han,
        thoi_gian_thu_hoi=None,
    )

    try:
        db.add(phien_moi)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi tạo phiên đăng nhập",
        )

    response.set_cookie(
        key=settings.ten_cookie_phien,
        value=ma_phien_goc,
        max_age=settings.thoi_han_phien_phut * 60,
        httponly=True,
        samesite="lax",
        path="/",
        secure=settings.cookie_phien_an_toan,
    )

    return PhanHoiDangNhap(
        authenticated=True,
        user=ThongTinNguoiDung(
            id=nguoi_dung.id,
            email=nguoi_dung.email,
            name=nguoi_dung.name,
            role=nguoi_dung.role,
        ),
    )


@router.get(
    "/session",
    status_code=status.HTTP_200_OK,
    response_model=PhanHoiPhien,
)
def kiem_tra_phien(
    request: Request,
    db: Session = Depends(get_db),
):
    ma_phien_goc = request.cookies.get(settings.ten_cookie_phien)
    if not ma_phien_goc:
        return PhanHoiPhien(authenticated=False, user=None)

    ma_bam = bam_ma_phien(ma_phien_goc)
    thoi_diem_hien_tai = datetime.now(timezone.utc)

    try:
        phien = db.scalar(
            select(PhienDangNhap).where(
                PhienDangNhap.ma_bam_phien == ma_bam,
                PhienDangNhap.thoi_gian_thu_hoi.is_(None),
                PhienDangNhap.thoi_gian_het_han > thoi_diem_hien_tai,
            )
        )
        if phien is None:
            return PhanHoiPhien(authenticated=False, user=None)

        nguoi_dung = db.scalar(
            select(User).where(User.id == phien.ma_nguoi_dung)
        )
        if nguoi_dung is None:
            return PhanHoiPhien(authenticated=False, user=None)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi kiểm tra phiên đăng nhập",
        )

    return PhanHoiPhien(
        authenticated=True,
        user=ThongTinNguoiDung(
            id=nguoi_dung.id,
            email=nguoi_dung.email,
            name=nguoi_dung.name,
            role=nguoi_dung.role,
        ),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=PhanHoiDangXuat,
)
def dang_xuat(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ma_phien_goc = request.cookies.get(settings.ten_cookie_phien)
    if ma_phien_goc:
        ma_bam = bam_ma_phien(ma_phien_goc)
        try:
            phien = db.scalar(
                select(PhienDangNhap).where(
                    PhienDangNhap.ma_bam_phien == ma_bam
                )
            )
            if phien is not None and phien.thoi_gian_thu_hoi is None:
                phien.thoi_gian_thu_hoi = datetime.now(timezone.utc)
                db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi hệ thống khi đăng xuất",
            )

    response.delete_cookie(
        key=settings.ten_cookie_phien,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_phien_an_toan,
    )

    return PhanHoiDangXuat(
        ok=True,
        authenticated=False,
    )
