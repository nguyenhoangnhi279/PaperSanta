"""
Embedding provider facade.

Switch providers/models from config without changing indexing or retrieval code.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseEmbeddingBackend(ABC):
    model_name: str
    dimension: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class SentenceTransformersBackend(BaseEmbeddingBackend):
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        logger.info(
            "Loading sentence-transformers embedding model: %s on %s",
            self.model_name,
            settings.EMBEDDING_DEVICE,
        )
        self.model = SentenceTransformer(
            self.model_name,
            device=settings.EMBEDDING_DEVICE,
        )
        logger.info("Embedding model loaded: %s", self.model_name)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(texts, show_progress_bar=False)
        if isinstance(embeddings, np.ndarray):
            embeddings = embeddings.tolist()
        vectors = [list(vector) for vector in embeddings]
        self._validate_dimensions(vectors)
        return vectors

    def _validate_dimensions(self, vectors: list[list[float]]) -> None:
        if not vectors:
            return
        actual_dimension = len(vectors[0])
        if actual_dimension != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: model returned {actual_dimension}, "
                f"but EMBEDDING_DIMENSION is {self.dimension}. Update config and DB schema together."
            )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"{settings.EMBEDDING_DOCUMENT_PREFIX}{text}" for text in texts]
        return self._encode(prefixed)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"{settings.EMBEDDING_QUERY_PREFIX}{text}"])[0]


class OpenAIEmbeddingBackend(BaseEmbeddingBackend):
    def __init__(self) -> None:
        from openai import OpenAI

        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")

        self.client = OpenAI(api_key=api_key)
        self.model_name = settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        logger.info("OpenAI embedding provider initialized: %s", self.model_name)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        request = {
            "model": self.model_name,
            "input": texts,
        }
        if settings.OPENAI_EMBEDDING_DIMENSIONS:
            request["dimensions"] = settings.OPENAI_EMBEDDING_DIMENSIONS

        response = self.client.embeddings.create(**request)
        vectors = [item.embedding for item in response.data]
        self._validate_dimensions(vectors)
        return vectors

    def _validate_dimensions(self, vectors: list[list[float]]) -> None:
        if not vectors:
            return
        actual_dimension = len(vectors[0])
        if actual_dimension != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: provider returned {actual_dimension}, "
                f"but EMBEDDING_DIMENSION is {self.dimension}. Update config and DB schema together."
            )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"{settings.EMBEDDING_DOCUMENT_PREFIX}{text}" for text in texts]
        return self._embed(prefixed)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"{settings.EMBEDDING_QUERY_PREFIX}{text}"])[0]


class EmbeddingProvider:
    _backend: BaseEmbeddingBackend | None = None
    _backend_key: tuple[str, str, int, str, str] | None = None

    @classmethod
    def get_backend(cls) -> BaseEmbeddingBackend:
        provider = settings.EMBEDDING_PROVIDER.lower().strip()
        backend_key = (
            provider,
            settings.EMBEDDING_MODEL_NAME,
            settings.EMBEDDING_DIMENSION,
            settings.EMBEDDING_QUERY_PREFIX,
            settings.EMBEDDING_DOCUMENT_PREFIX,
        )
        if cls._backend is not None and cls._backend_key == backend_key:
            return cls._backend

        if provider in {"sentence-transformers", "sentence_transformers", "local"}:
            cls._backend = SentenceTransformersBackend()
        elif provider == "openai":
            cls._backend = OpenAIEmbeddingBackend()
        else:
            raise ValueError(
                "Unsupported EMBEDDING_PROVIDER. Use 'sentence-transformers' or 'openai'."
            )

        cls._backend_key = backend_key
        return cls._backend

    @classmethod
    def embed_documents(cls, texts: list[str]) -> list[list[float]]:
        vectors = cls.get_backend().embed_documents(texts)
        logger.debug("Embedded %s documents, dim=%s", len(vectors), len(vectors[0]) if vectors else 0)
        return vectors

    @classmethod
    def embed_query(cls, text: str) -> list[float]:
        vector = cls.get_backend().embed_query(text)
        logger.debug("Embedded query, dim=%s", len(vector))
        return vector

    @classmethod
    def embed_texts(cls, texts: list[str]) -> list[list[float]]:
        return cls.embed_documents(texts)

    @classmethod
    def embed_text(cls, text: str) -> list[float]:
        return cls.embed_query(text)

    @classmethod
    def warmup(cls, text: str | None = None) -> dict:
        warmup_text = text or settings.EMBEDDING_WARMUP_TEXT
        start = time.perf_counter()
        backend = cls.get_backend()
        vector = backend.embed_query(warmup_text)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        result = {
            "provider": settings.EMBEDDING_PROVIDER,
            "model": backend.model_name,
            "dimension": len(vector),
            "elapsed_ms": elapsed_ms,
        }
        logger.info(
            "Embedding warmup completed: provider=%s model=%s dim=%s elapsed=%sms",
            result["provider"],
            result["model"],
            result["dimension"],
            result["elapsed_ms"],
        )
        return result
