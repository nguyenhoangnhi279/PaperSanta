"""
embedding_provider.py — Singleton quản lý sentence-transformers model
Model được load lazy lần đầu gọi, cache lại cho các request sau
"""

import logging
import numpy as np
from functools import lru_cache
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    _model = None
    _model_name: str = ""

    @classmethod
    def get_model(cls):
        if cls._model is None or cls._model_name != settings.EMBEDDING_MODEL_NAME:
            from sentence_transformers import SentenceTransformer
            logger.info(
                f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME} "
                f"on {settings.EMBEDDING_DEVICE}..."
            )
            cls._model = SentenceTransformer(
                settings.EMBEDDING_MODEL_NAME,
                device=settings.EMBEDDING_DEVICE,
            )
            cls._model_name = settings.EMBEDDING_MODEL_NAME
            logger.info(f"Model loaded: {settings.EMBEDDING_MODEL_NAME}")
        return cls._model

    @classmethod
    def embed_texts(cls, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = cls.get_model()
        embeddings = model.encode(texts, show_progress_bar=False)
        if isinstance(embeddings, np.ndarray):
            embeddings = embeddings.tolist()
        logger.debug(f"Embedded {len(texts)} texts, dim={len(embeddings[0]) if embeddings else 0}")
        return embeddings

    @classmethod
    def embed_text(cls, text: str) -> list[float]:
        return cls.embed_texts([text])[0]
