import asyncio
import random
from collections.abc import AsyncGenerator

from google import genai
from google.genai import types

from src.config import settings
from src.middleware.error_handler import LLMServiceError
from src.middleware.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful and precise document assistant. "
    "Answer questions based ONLY on the provided context from uploaded documents.\n\n"
    "Rules:\n"
    "- Base your answers strictly on the provided context\n"
    "- If the context does not contain enough information, say so clearly\n"
    "- Cite which document(s) your answer comes from\n"
    "- If previous conversation history is provided, use it for conversational coherence\n"
    "- Be concise, professional, and well-structured\n"
    "- Use markdown formatting (bullet points, bold highlights) for clarity\n"
    "- Never hallucinate or make up information not present in the context"
)

RETRYABLE_MARKERS = ("429", "resource_exhausted", "503", "unavailable", "500", "internal")
MAX_ATTEMPTS = 4
BASE_BACKOFF_SECONDS = 2.0

RATE_LIMITED_MESSAGE = (
    "The AI service is currently rate-limited. Please wait a moment and try again."
)
QUOTA_EXHAUSTED_MESSAGE = (
    "The daily quota for the configured AI model has been used up. "
    "Try again after the quota resets, or switch LLM_MODEL to another model."
)
UNAVAILABLE_MESSAGE = "The AI service is temporarily unavailable. Please try again shortly."
GENERIC_MESSAGE = "The AI service could not complete this request."

QUERY_TEMPLATE = """Context from uploaded documents:
---
{context}
---
{history_section}
User Question: {question}

Provide a detailed, grounded answer based on the context above. Reference the source documents."""


class LLMService:
    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def initialize(self) -> None:
        if not settings.gemini_api_key:
            raise LLMServiceError("GEMINI_API_KEY is not configured")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("llm_service_initialized", model=settings.llm_model)

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            raise LLMServiceError("LLM service not initialized")
        return self._client

    def build_prompt(
        self,
        question: str,
        context_chunks: list[dict],
        chat_history: list[dict] | None = None,
    ) -> str:
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            source = chunk.get("document_name", "Unknown")
            content = chunk.get("content", "")
            context_parts.append(f"[Source {i}: {source}]\n{content}")

        context = "\n\n".join(context_parts)

        history_section = ""
        if chat_history:
            history_lines = []
            for msg in chat_history[-6:]:
                role_label = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                history_lines.append(f"{role_label}: {content}")
            history_section = (
                "Prior Conversation History:\n" + "\n".join(history_lines) + "\n---\n"
            )

        return QUERY_TEMPLATE.format(
            context=context,
            history_section=history_section,
            question=question,
        )

    def _get_config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=1500,
        )

    @staticmethod
    def _user_message(exc: Exception) -> str:
        detail = str(exc).lower()
        if "429" in detail or "resource_exhausted" in detail:
            if "perday" in detail.replace("_", "").replace("-", ""):
                return QUOTA_EXHAUSTED_MESSAGE
            return RATE_LIMITED_MESSAGE
        if "503" in detail or "unavailable" in detail:
            return UNAVAILABLE_MESSAGE
        return GENERIC_MESSAGE

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(marker in message for marker in RETRYABLE_MARKERS)

    @staticmethod
    async def _backoff(attempt: int) -> None:
        delay = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
        await asyncio.sleep(delay + random.uniform(0, 0.5))

    async def generate(self, prompt: str) -> str:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=settings.llm_model,
                    contents=prompt,
                    config=self._get_config(),
                )
                return response.text or ""
            except Exception as exc:
                if attempt < MAX_ATTEMPTS and self._is_retryable(exc):
                    logger.warning("llm_generation_retry", attempt=attempt, error=str(exc)[:200])
                    await self._backoff(attempt)
                    continue
                logger.error("llm_generation_failed", error=str(exc))
                raise LLMServiceError(self._user_message(exc)) from exc
        raise LLMServiceError(RATE_LIMITED_MESSAGE)

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model=settings.llm_model,
                    contents=prompt,
                    config=self._get_config(),
                )
            except Exception as exc:
                if attempt < MAX_ATTEMPTS and self._is_retryable(exc):
                    logger.warning("llm_stream_retry", attempt=attempt, error=str(exc)[:200])
                    await self._backoff(attempt)
                    continue
                logger.error("llm_stream_failed", error=str(exc))
                raise LLMServiceError(self._user_message(exc)) from exc

            try:
                async for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as exc:
                logger.error("llm_stream_interrupted", error=str(exc))
                raise LLMServiceError(self._user_message(exc)) from exc


llm_service = LLMService()
