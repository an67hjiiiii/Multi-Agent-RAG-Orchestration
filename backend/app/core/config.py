from dataclasses import dataclass
from os import getenv
from pathlib import Path
from dotenv import load_dotenv

_backend_dir = Path(__file__).resolve().parent.parent.parent
_root_dir = _backend_dir.parent
if (_root_dir / ".env").exists():
    load_dotenv(_root_dir / ".env")
elif (_backend_dir / ".env").exists():
    load_dotenv(_backend_dir / ".env")
else:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = getenv("APP_NAME", "Multi-Agent RAG Orchestration")
    app_env: str = getenv("APP_ENV", "development")
    backend_host: str = getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(getenv("BACKEND_PORT", "8000"))
    database_url: str = getenv("DATABASE_URL", "")
    ollama_base_url: str = getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = getenv("OLLAMA_MODEL", "")
    cors_origins: str = getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    ten_cookie_phien: str = "capone_session"
    thoi_han_phien_phut: int = 60
    cookie_phien_an_toan: bool = getenv("SESSION_COOKIE_SECURE", "false").lower() in (
        "true",
        "1",
        "yes",
    )


settings = Settings()
