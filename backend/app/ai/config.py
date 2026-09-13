import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, SecretStr

from app.ai.interview.engine import InterviewEngine
from app.ai.interview.schemas import Model
from app.ai.interview.state import InMemoryInterviewStore, InterviewService, InterviewStore
from app.ai.llm.client import LLMClient
from app.ai.llm.mock import MockProvider

load_dotenv()


class Settings(Model):
    provider: Literal["mock", "gemini"] = "gemini"
    api_key: SecretStr = SecretStr("")
    model: str = "gemini-3.6-flash"
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_turns: int = Field(default=40, ge=1, le=100)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            provider=os.getenv("M2_LLM_PROVIDER", "gemini"),
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            timeout_seconds=os.getenv("M2_LLM_TIMEOUT_SECONDS", "30"),
            max_turns=os.getenv("M2_MAX_TURNS", "40"),
        )


def get_settings() -> Settings:
    return Settings.from_env()


def build_service(
    settings: Settings | None = None,
    *,
    provider: LLMClient | None = None,
    store: InterviewStore | None = None,
) -> InterviewService:
    """Compose M2 with replaceable provider and persistence ports.

    A caller can inject another transaction-backed InterviewStore without changing
    the interview domain. The production composition uses durable SQLite storage.
    """
    settings = settings or Settings.from_env()
    if provider is None:
        if settings.provider == "mock":
            provider = MockProvider()
        else:
            from app.ai.llm.gemini_provider import GeminiProvider

            provider = GeminiProvider(
                settings.api_key.get_secret_value(), settings.model, settings.timeout_seconds
            )
    return InterviewService(
        InterviewEngine(provider, max_turns=settings.max_turns),
        store if store is not None else InMemoryInterviewStore(),
    )
