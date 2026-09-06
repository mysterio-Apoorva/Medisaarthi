import os
from typing import Literal

from pydantic import Field, SecretStr
from dotenv import load_dotenv

from app.interview.engine import InterviewEngine
from app.interview.schemas import Model
from app.interview.state import InMemoryInterviewStore, InterviewService, InterviewStore
from app.llm.client import LLMClient
from app.llm.mock import MockProvider


load_dotenv()


class Settings(Model):
    provider: Literal["mock", "gemini"] = "mock"
    api_key: SecretStr = SecretStr("")
    model: str = "gemini-3.6-flash"
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_turns: int = Field(default=40, ge=1, le=100)

    @classmethod
    def from_env(cls) -> "Settings":
        model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        if model.removeprefix("models/") == "gemini-2.5-flash":
            model = "gemini-3.6-flash"
        return cls(
            provider=os.getenv("M2_LLM_PROVIDER", "mock"),
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=model,
            timeout_seconds=os.getenv("M2_LLM_TIMEOUT_SECONDS", "30"),
            max_turns=os.getenv("M2_MAX_TURNS", "40"),
        )


def build_service(
    settings: Settings | None = None,
    *,
    provider: LLMClient | None = None,
    store: InterviewStore | None = None,
) -> InterviewService:
    """Compose M2 with replaceable provider and persistence ports.

    M3 can inject a transaction-backed InterviewStore without importing FastAPI or
    changing the interview domain. Defaults remain safe for an offline demo.
    """
    settings = settings or Settings.from_env()
    if provider is None:
        if settings.provider == "mock":
            provider = MockProvider()
        else:
            from app.llm.gemini_provider import GeminiProvider

            provider = GeminiProvider(
                settings.api_key.get_secret_value(), settings.model, settings.timeout_seconds
            )
    return InterviewService(
        InterviewEngine(provider, max_turns=settings.max_turns),
        store if store is not None else InMemoryInterviewStore(),
    )
