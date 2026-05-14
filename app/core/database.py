"""
database.py — SQLAlchemy async engine + session factory
Kết nối Supabase PostgreSQL qua connection pooler (port 6543)
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=settings.DB_ECHO,           # log SQL khi DEBUG=True
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,              # tự reconnect nếu connection chết
    connect_args={
        "ssl": "require",            # Supabase bắt buộc SSL
        "timeout": 10,               # Connection timeout 10s
        "command_timeout": 10,       # Command timeout 10s
        "statement_cache_size": 0,   # Tắt prepared statements cho pgbouncer
        "prepared_statement_cache_size": 0,  # asyncpg compatibility
    },
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Dependency injection cho FastAPI ─────────────────────────────────────────
async def get_db() -> AsyncSession:
    """Dùng trong FastAPI route: Depends(get_db)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Tạo tất cả tables nếu chưa tồn tại"""
    try:
        async with engine.begin() as conn:
            logger.info("Checking/Initializing database tables...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            
            await conn.run_sync(Base.metadata.create_all)
            
    except Exception as e:
        logger.error("Critial Error: Could not connect to Supabase Database!")
        logger.error(f"Reason: {e}")

async def drop_db():
    """Dùng khi test: xóa tất cả tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All tables dropped.")


from app.models.pdf_document import PDFDocument  # noqa: E402, F401
from app.models.embedding import PDFChunk, PDFEmbedding  # noqa: E402, F401
from app.models.chat import ChatSession, ChatMessage, SessionPDF, MessageCitation  # noqa: E402, F401
from app.models.analysis import MultiAnalysis, AnalysisDocument  # noqa: E402, F401