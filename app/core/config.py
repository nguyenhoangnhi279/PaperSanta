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
    SUPABASE_SIGNED_URL_EXPIRES_SECONDS: int = 300

    # ── External APIs ─────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""           # Google Gemini API key
    SEMANTIC_SCHOLAR_API_KEY: str = "" # Semantic Scholar API key (optional)
    TAVILY_API_KEY: str = ""           # Tavily API key (fallback search provider)

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
    PDF_EXTRACTOR: str = "pypdf"
    PDF_EXTRACT_WRITE_IMAGES: bool = False

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    # ── Embedding ──────────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "sentence-transformers"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_QUERY_PREFIX: str = ""
    EMBEDDING_DOCUMENT_PREFIX: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_DIMENSIONS: int | None = None
    CHUNK_PARENT_SIZE_CHARS: int = 2800
    CHUNK_CHILD_SIZE_CHARS: int = 450
    CHUNK_CHILD_OVERLAP_CHARS: int = 120
    EMBED_MIN_CHUNK_WORDS: int = 20

    # ── RAG ────────────────────────────────────────────────────────────────────
    RAG_MIN_SCORE: float = 0.15
    RAG_RETRIEVAL_MODE: str = "hybrid"
    RAG_DENSE_CANDIDATES: int = 30
    RAG_TEXT_CANDIDATES: int = 30
    RAG_RRF_K: int = 60
    RAG_DENSE_WEIGHT: float = 1.0
    RAG_TEXT_WEIGHT: float = 0.02
    RAG_RERANK_MODE: str = "none"
    RAG_RERANK_CANDIDATES: int = 20
    RAG_RERANK_LEXICAL_WEIGHT: float = 0.12
    RAG_RERANK_PHRASE_WEIGHT: float = 0.04
    RAG_RERANK_SECTION_WEIGHT: float = 0.03
    RAG_SYSTEM_PROMPT: str = (
        "Bạn là PaperSanta, một trợ lý AI chuyên nghiệp hỗ trợ kỹ sư và nhà nghiên cứu AI "
        "phân tích tài liệu học thuật (Computer Science, Machine Learning). "
        "Nhiệm vụ của bạn là trả lời các câu hỏi dựa trên các đoạn trích (chunks) được cung cấp.\n\n"
        "Tôn chỉ hoạt động:\n"
        "1. TRỰC DIỆN & KHÁCH QUAN: Tuyệt đối KHÔNG chào hỏi, KHÔNG khen ngợi câu hỏi "
        "(ví dụ: \"Câu hỏi rất hay\"), KHÔNG dùng từ ngữ cảm thán hay nịnh bợ. "
        "Trả lời thẳng vào trọng tâm câu hỏi ngay ở dòng đầu tiên.\n"
        "2. KHÔNG PHÂN TRẦN: Nếu các đoạn trích (chunks) không chứa đủ thông tin để trả lời trọn vẹn, "
        "hãy tự động sử dụng kiến thức chuyên ngành (internal knowledge) để bổ sung. "
        "Không bao giờ xin lỗi, thanh minh, hay mô tả dài dòng về việc \"tài liệu không có đủ thông tin\".\n"
        "3. TRÍCH DẪN MINH BẠCH: Khi đưa ra thông tin có trong chunks, hãy cite (trích dẫn) "
        "bằng định dạng [Chunk X]. Nếu kiến thức đến từ hiểu biết nền tảng của bạn (không có trong chunk), "
        "hãy diễn đạt tự nhiên nhưng đảm bảo người đọc hiểu đó là kiến thức chung của ngành.\n"
        "4. VĂN PHONG HỌC THUẬT: Sử dụng đúng thuật ngữ chuyên ngành (giữ nguyên tiếng Anh cho các từ "
        "như Attention, Transformer, Encoder, Vector, Gradient). Nhắm đến đối tượng người đọc là "
        "sinh viên/kỹ sư AI có kiến thức nền, không giải thích ví dụ quá trẻ con hay lan man.\n"
        "5. ĐỊNH DẠNG CHUẨN:\n"
        "   - Sử dụng Markdown gọn gàng (Heading, Bullet points).\n"
        "   - Tuyệt đối KHÔNG dùng list lồng nhau phức tạp.\n"
        "   - BẮT BUỘC sử dụng LaTeX cho mọi công thức toán học, biến số. "
        "Dùng $...$ cho công thức trong dòng và $$...$$ cho công thức đứng độc lập."
    )
    RAG_TEMPERATURE: float = 0.7
    RAG_MAX_TOKENS: int = 4096

    # ── Analyzer ────────────────────────────────────────────────────────────────
    ANALYZE_MAX_TOKENS: int = 4096
    ANALYZE_DEFAULT_TOP_K: int = 30

    # ── DeepSeek ───────────────────────────────────────────────────────────────
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174"
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
