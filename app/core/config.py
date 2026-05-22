"""
config.py — Tập trung toàn bộ cấu hình, đọc từ .env
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "PaperSanta PDF Service"
    DEBUG: bool = False
    DB_ECHO: bool = False             # True = in SQL ra console, bật khi debug

    # ── Database (Supabase) ───────────────────────────────────────────────────
    DB_HOST: str = ""
    DB_PORT: int = 6543
    DB_NAME: str = "postgres"
    DB_USER: str = ""
    DB_PASSWORD: str = ""

    # ── Supabase Auth & Storage ───────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""             # anon public key (dùng cho frontend)
    SUPABASE_SERVICE_ROLE_KEY: str = "" # service_role key (dùng backend storage)
    SUPABASE_JWT_SECRET: str = ""      # để verify JWT server-side
    SUPABASE_STORAGE_BUCKET: str = "pdfs"

    # ── External APIs ─────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""           # Google Gemini API key
    SEMANTIC_SCHOLAR_API_KEY: str = "" # Semantic Scholar API key (optional)

    @property
    def database_url(self) -> str:
        # asyncpg driver cho SQLAlchemy async
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ── File Upload ───────────────────────────────────────────────────────────
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = ["pdf"]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.env"),
        "env_file_encoding": "utf-8",
        "extra":"ignore"  # Bỏ qua các field không khai báo trong .env
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Helper để clear cache khi cần (development only)
def reload_settings():
    get_settings.cache_clear()
    global settings
    settings = get_settings()
    return settings
