from unittest.mock import MagicMock
import pytest
from sqlalchemy import text

from app.db.safety import get_target_database_url, verify_alembic_safety_guard


def test_guard_is_noop_in_standard_mode(monkeypatch: pytest.MonkeyPatch):
    """Khi không thiết lập TARGET_TEST_DB, guard không can thiệp vào hành vi migration chuẩn."""
    monkeypatch.delenv("TARGET_TEST_DB", raising=False)
    mock_conn = MagicMock()
    # Không ném lỗi
    verify_alembic_safety_guard(mock_conn, "postgresql://user:pass@localhost:5432/multi_agent_rag")
    # Connection không cần phải bị truy vấn
    mock_conn.execute.assert_not_called()


def test_guard_blocks_url_pointing_to_multi_agent_rag(monkeypatch: pytest.MonkeyPatch):
    """Ở chế độ test chunk, nếu URL trỏ vào multi_agent_rag thì bị chặn ngay lập tức."""
    monkeypatch.setenv("TARGET_TEST_DB", "multi_agent_rag_chunk_test")
    mock_conn = MagicMock()

    url = "postgresql://user:pass@localhost:5432/multi_agent_rag"
    with pytest.raises(
        RuntimeError,
        match="URL tro vao 'multi_agent_rag', khong khop expected test database 'multi_agent_rag_chunk_test'",
    ):
        verify_alembic_safety_guard(mock_conn, url)

    # Đảm bảo chưa thực thi câu lệnh SQL nào trên connection
    mock_conn.execute.assert_not_called()


def test_guard_blocks_url_pointing_to_multi_agent_rag_test(monkeypatch: pytest.MonkeyPatch):
    """Ở chế độ test chunk, nếu URL trỏ vào multi_agent_rag_test thì bị chặn ngay lập tức."""
    monkeypatch.setenv("TARGET_TEST_DB", "multi_agent_rag_chunk_test")
    mock_conn = MagicMock()

    url = "postgresql://user:pass@localhost:5432/multi_agent_rag_test"
    with pytest.raises(
        RuntimeError,
        match="URL tro vao 'multi_agent_rag_test', khong khop expected test database 'multi_agent_rag_chunk_test'",
    ):
        verify_alembic_safety_guard(mock_conn, url)

    mock_conn.execute.assert_not_called()


def test_guard_blocks_invalid_host(monkeypatch: pytest.MonkeyPatch):
    """Chặn nếu host không phải localhost hoặc 127.0.0.1."""
    monkeypatch.setenv("TARGET_TEST_DB", "multi_agent_rag_chunk_test")
    mock_conn = MagicMock()

    url = "postgresql://user:pass@192.168.1.100:5432/multi_agent_rag_chunk_test"
    with pytest.raises(RuntimeError, match="Host khong hop le cho kiem thu: '192.168.1.100'"):
        verify_alembic_safety_guard(mock_conn, url)

    mock_conn.execute.assert_not_called()


def test_guard_blocks_when_actual_connection_database_mismatches(monkeypatch: pytest.MonkeyPatch):
    """
    Kịch bản then chốt (Root Cause Fix):
    Nếu URL khai báo multi_agent_rag_chunk_test nhưng connection thực tế trả về multi_agent_rag,
    guard phải phát hiện và chặn đứng lập tức!
    """
    monkeypatch.setenv("TARGET_TEST_DB", "multi_agent_rag_chunk_test")
    mock_conn = MagicMock()
    # Giả lập connection thực tế trả về multi_agent_rag khi chạy SELECT current_database()
    mock_conn.execute.return_value.scalar.return_value = "multi_agent_rag"

    url = "postgresql://user:pass@localhost:5432/multi_agent_rag_chunk_test"
    with pytest.raises(RuntimeError, match="current_database\\(\\) tren connection thuc te la 'multi_agent_rag'"):
        verify_alembic_safety_guard(mock_conn, url)


def test_guard_blocks_when_actual_connection_returns_multi_agent_rag_test(monkeypatch: pytest.MonkeyPatch):
    """Connection thực tế trả về multi_agent_rag_test bị chặn đứng."""
    monkeypatch.setenv("TARGET_TEST_DB", "multi_agent_rag_chunk_test")
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = "multi_agent_rag_test"

    url = "postgresql://user:pass@localhost:5432/multi_agent_rag_chunk_test"
    with pytest.raises(RuntimeError, match="current_database\\(\\) tren connection thuc te la 'multi_agent_rag_test'"):
        verify_alembic_safety_guard(mock_conn, url)


def test_guard_passes_when_all_conditions_match_multi_agent_rag_chunk_test(monkeypatch: pytest.MonkeyPatch):
    """Khi cả URL, host localhost và connection thực tế đều là multi_agent_rag_chunk_test, guard cho phép tiếp tục."""
    monkeypatch.setenv("TARGET_TEST_DB", "multi_agent_rag_chunk_test")
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = "multi_agent_rag_chunk_test"

    url = "postgresql://user:pass@localhost:5432/multi_agent_rag_chunk_test"
    # Không ném ngoại lệ
    verify_alembic_safety_guard(mock_conn, url)

    # Đảm bảo đã thực thi SELECT current_database() để xác minh connection thật
    mock_conn.execute.assert_called_once()


def test_get_target_database_url_precedence(monkeypatch: pytest.MonkeyPatch):
    """Kiểm tra thứ tự ưu tiên: biến môi trường DATABASE_URL được ưu tiên cao nhất."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://custom_user:custom_pass@localhost:5432/multi_agent_rag_chunk_test")
    url = get_target_database_url()
    assert url == "postgresql+psycopg://custom_user:custom_pass@localhost:5432/multi_agent_rag_chunk_test"
