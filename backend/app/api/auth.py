from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,EmailStr

router=APIRouter(tags=["auth"])
class YeuCauDangKy(BaseModel):
    email:EmailStr
    password:str
@router.post("/register",status_code=201)

def dang_ky_nguoi_dung(payload:YeuCauDangKy):
    if payload.email == "":
        raise HTTPException(
            status_code=400,
            detail="Email không được để trống"
        )
    if payload.password=="":
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu không được để trống"
        )
    return{
        "email":payload.email,
        "message":"Đăng ký thành công"
    }