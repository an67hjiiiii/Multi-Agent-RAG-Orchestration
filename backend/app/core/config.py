from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str = getenv("APP_NAME", "Multi-Agent RAG Orchestration")
    app_env: str = getenv("APP_ENV", "development")
    backend_host: str = getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(getenv("BACKEND_PORT", "8000"))
    database_url: str = getenv("DATABASE_URL", "")
    ollama_base_url: str = getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = getenv("OLLAMA_MODEL", "")


settings = Settings()
