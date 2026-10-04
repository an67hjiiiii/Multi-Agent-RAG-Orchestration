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
