"""
deepseek_provider.py — Singleton gọi DeepSeek API (compatible với OpenAI format)
"""

import logging
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepSeekProvider:
    _client: OpenAI | None = None

    @classmethod
    def get_client(cls) -> OpenAI:
        if cls._client is None:
            if not settings.DEEPSEEK_API_KEY:
                raise ValueError("DEEPSEEK_API_KEY chưa được cấu hình trong .env")
            cls._client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_API_BASE,
            )
            logger.info(f"DeepSeek client initialized: {settings.DEEPSEEK_API_BASE}")
        return cls._client

    @classmethod
    def generate(
        cls,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> tuple[str, int, int]:
        client = cls.get_client()
        logger.debug(f"Calling DeepSeek: temp={temperature}, max_tokens={max_tokens}")

        response = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        answer = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        logger.info(
            f"DeepSeek response: {len(answer)} chars, "
            f"{prompt_tokens} in / {completion_tokens} out"
        )
        return answer, prompt_tokens, completion_tokens
