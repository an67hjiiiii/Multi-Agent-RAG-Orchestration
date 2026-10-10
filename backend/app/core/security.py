import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def bam_mat_khau(mat_khau: str) -> str:
    return _hasher.hash(mat_khau)


def xac_thuc_mat_khau(mat_khau_chua_bam: str, mat_khau_da_bam: str) -> bool:
    try:
        return _hasher.verify(mat_khau_da_bam, mat_khau_chua_bam)
    except (VerifyMismatchError, InvalidHashError):
        return False


def tao_ma_phien() -> str:
    return secrets.token_urlsafe(32)


def bam_ma_phien(ma_phien: str) -> str:
    return hashlib.sha256(ma_phien.encode("utf-8")).hexdigest()

