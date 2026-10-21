import logging
import os
from sqlalchemy import text
from sqlalchemy.engine import make_url

logger = logging.getLogger("alembic.env")


def get_target_database_url(default_url: str | None = None) -> str:
    """
    Xác định URL kết nối thực tế cho Alembic:
    Ưu tiên 1: os.getenv("DATABASE_URL")
    Ưu tiên 2: default_url được cấu hình
    """
    url = os.getenv("DATABASE_URL") or default_url or ""
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def verify_alembic_safety_guard(connection, target_url: str) -> None:
    """
    Fail-Closed Safety Guard cho Alembic Migration:
    Khi biến môi trường TARGET_TEST_DB được thiết lập (chế độ kiểm thử có bảo vệ):
    1. Kiểm tra URL target: host phải là localhost hoặc 127.0.0.1.
    2. URL database name bắt buộc phải khớp TARGET_TEST_DB.
    3. Thực thi 'SELECT current_database()' trực tiếp trên chính connection đưa vào Alembic.
    4. Chặn đứng và ném lỗi nếu actual_db khác TARGET_TEST_DB.
    5. Chặn đứng nếu actual_db là protected databases ('multi_agent_rag', 'multi_agent_rag_test')
       trong khi TARGET_TEST_DB kỳ vọng database khác.
    """
    expected_test_db = os.getenv("TARGET_TEST_DB")
    if not expected_test_db:
        return

    url_obj = make_url(target_url)
    host = url_obj.host
    db_in_url = url_obj.database

    if host not in ("localhost", "127.0.0.1"):
        raise RuntimeError(
            f"[ALEMBIC SAFETY GUARD] Host khong hop le cho kiem thu: '{host}'. Chi chap nhan localhost hoac 127.0.0.1"
        )

    if db_in_url != expected_test_db:
        raise RuntimeError(
            f"[ALEMBIC SAFETY GUARD] URL tro vao '{db_in_url}', khong khop expected test database '{expected_test_db}'"
        )

    # Truy vấn trực tiếp trên connection thực tế
    actual_db = connection.execute(text("SELECT current_database();")).scalar()
    if actual_db != expected_test_db:
        raise RuntimeError(
            f"[ALEMBIC SAFETY GUARD] current_database() tren connection thuc te la '{actual_db}', "
            f"khong phai '{expected_test_db}'! CHẶN ĐỨNG MIGRATION."
        )

    if actual_db in ("multi_agent_rag", "multi_agent_rag_test") and actual_db != expected_test_db:
        raise RuntimeError(
            f"[ALEMBIC SAFETY GUARD] NGUY HIEM: Phat hien ket noi toi protected database '{actual_db}'! CHẶN ĐỨNG."
        )

    logger.info(
        "[ALEMBIC SAFETY GUARD] Verified connection: host=%s, database=%s (MATCHES expected '%s')",
        host,
        actual_db,
        expected_test_db,
    )
