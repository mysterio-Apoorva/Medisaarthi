"""Replaceable, server-side-only AI providers.

Ollama is the default zero-cost path.  Every model result is treated as an
untrusted suggestion and is validated before the clinical engine receives it.
"""

from __future__ import annotations

import json
import os
import time
import re
from threading import Lock
from urllib.parse import urlparse
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from backend.app.clinical_engine import BOOL_FIELDS, LIST_FIELDS, extract_rule_based, _severity, UNKNOWN_WORDS, DECLINED_WORDS


class ExtractedFact(BaseModel):
    field_name: str = Field(min_length=1, max_length=64)
    value: str | int | bool | list[str]
    evidence: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class StructuredExtraction(BaseModel):
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=20)


class AIProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def structured_output(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        return schema.model_validate_json(self.generate(prompt))

    def tool_call(self, prompt: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("This provider does not expose tool calling")

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError("This provider does not expose embeddings")

    def extract(self, statement: str, question_id: str, state: dict[str, Any]) -> StructuredExtraction:
        # The rule engine is the safety boundary for clinical state.  It has
        # explicit type/field semantics and is intentionally evaluated even
        # when an LLM is available.  The model may help with the patient's
        # language, but it can never overwrite a deterministic, grounded
        # interpretation of the question currently being asked.
        rule_facts = extract_rule_based(statement, question_id, state)
        prompt = (
            "Extract only clinical facts explicitly stated by the patient. Do not infer, diagnose, "
            "or fill gaps. Return JSON matching {facts:[{field_name,value,evidence,confidence}]}. "
            f"Question field: {question_id}. Patient statement: {statement!r}. Current state: {json.dumps(state)}"
        )
        result = self.structured_output(prompt, StructuredExtraction)
        statement_folded = statement.casefold()
        model_facts = [
            fact
            for fact in result.facts
            if _is_safe_model_fact(fact, statement_folded, question_id, state.get('_question_fields'))
        ]

        # A model response is never allowed to replace a validated clinical
        # rule result.  It may only fill the one field the patient was asked
        # about when that field was not understood by the local parser.
        merged = {fact["field_name"]: fact for fact in rule_facts}
        for fact in model_facts:
            merged.setdefault(
                fact.field_name,
                {
                    **fact.model_dump(),
                    "source": "AI_EXTRACTION",
                },
            )
        return StructuredExtraction.model_validate({"facts": list(merged.values())})


def _is_safe_model_fact(fact: ExtractedFact, statement_folded: str, question_id: str, fields: list[str] | None = None) -> bool:
    """Accept only grounded, type-safe output for the active question.

    Structured JSON only proves that an LLM response can be parsed; it does
    not prove that its medical meaning is correct.  This narrow allow-list
    keeps a model from storing an unrelated fact (for example using
    ``chest_pain`` as a field for a chief-complaint answer) or assigning an
    arbitrary string to a boolean/severity field.
    """
    if fact.field_name not in (fields or [question_id]):
        return False
    question_id = fact.field_name
    if fields and len(fields) > 1 and statement_folded.strip(' .!') in {'yes', 'yeah', 'हाँ', 'हां'}:
        # A yes to a compound question does not establish which symptom/condition is present.
        return False
    if any(word in statement_folded for word in UNKNOWN_WORDS + DECLINED_WORDS):
        return False
    evidence = fact.evidence.strip().casefold()
    if not evidence or evidence not in statement_folded:
        return False
    if question_id in BOOL_FIELDS:
        return isinstance(fact.value, bool)
    if question_id in LIST_FIELDS:
        if not isinstance(fact.value, list): return False
        if not fact.value:
            return bool(re.search(r'\b(?:no|none|nothing|nahi|nahin)\b|नहीं', evidence))
        return all(isinstance(item, str) and item.strip() and item.casefold().strip() in statement_folded for item in fact.value)
    if question_id == "severity":
        return type(fact.value) is int and _severity(statement_folded, True) == fact.value
    return isinstance(fact.value, str) and bool(fact.value.strip()) and fact.value.casefold().strip() in statement_folded


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float = 20) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("AI_MODEL", "qwen2.5:3b-instruct")
        self.timeout = timeout

    def _assert_private_destination(self):
        if urlparse(self.base_url).hostname not in {'localhost','127.0.0.1','::1'} and os.getenv('ALLOW_EXTERNAL_AI', 'false').lower() != 'true':
            raise RuntimeError('External AI processing requires explicit configuration')

    def generate(self, prompt: str) -> str:
        self._assert_private_destination()
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        content = response.json().get("response")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned no structured content")
        return content

    def structured_output(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        self._assert_private_destination()
        response = httpx.post(f'{self.base_url}/api/generate', json={'model':self.model, 'prompt':prompt, 'stream':False, 'format':schema.model_json_schema(), 'options':{'temperature':0}}, timeout=self.timeout)
        response.raise_for_status()
        return schema.model_validate_json(response.json().get('response', ''))

    def tool_call(self, prompt: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
        self._assert_private_destination()
        response = httpx.post(f'{self.base_url}/api/chat', json={'model':self.model,'stream':False,'messages':[{'role':'user','content':prompt}],'tools':tools,'options':{'temperature':0}}, timeout=self.timeout)
        response.raise_for_status()
        calls = response.json().get('message',{}).get('tool_calls',[])
        allowed = {tool.get('function',{}).get('name') for tool in tools}
        if any(call.get('function',{}).get('name') not in allowed for call in calls):
            raise ValueError('Model selected a tool outside the allowlist')
        return {'tool_calls':calls}

    def embed(self, text: str) -> list[float]:
        self._assert_private_destination()
        response = httpx.post(
            f"{self.base_url}/api/embed", json={"model": os.getenv('EMBEDDING_MODEL','all-minilm'), "input": text}, timeout=self.timeout
        )
        response.raise_for_status()
        values = response.json().get("embeddings", [[]])
        return values[0] if values and isinstance(values[0], list) else []


class RuleBasedProvider(AIProvider):
    """Honest offline fallback, labeled as rules rather than a model."""
    name = "clinical_rules"

    def generate(self, prompt: str) -> str:
        raise RuntimeError("Natural-language generation requires a configured AI provider")

    def extract(self, statement: str, question_id: str, state: dict[str, Any]) -> StructuredExtraction:
        return StructuredExtraction.model_validate({"facts": extract_rule_based(statement, question_id, state)})


def configured_provider() -> AIProvider:
    if os.getenv("AI_PROVIDER", "ollama").casefold() == "ollama":
        return OllamaProvider()
    return RuleBasedProvider()


class ProviderManager:
    """Configured local-model priority, bounded cooldowns, and non-sensitive health metrics."""
    def __init__(self):
        self.health: dict[str,dict[str,Any]] = {}
        self.lock = Lock()

    def snapshot(self):
        with self.lock:
            return [{'provider':'ollama','model':key,**{k:v for k,v in value.items() if k!='until'},'cooldown_seconds':max(0,round(value.get('until',0)-time.monotonic()))} for key,value in self.health.items()]

    def extract(self,statement,question_id,state):
        primary = configured_provider()
        if isinstance(primary,RuleBasedProvider):
            return primary.extract(statement,question_id,state), primary.name, None
        candidates=[primary]+[OllamaProvider(model=name.strip()) for name in os.getenv('AI_FALLBACK_MODELS','').split(',') if name.strip() and name.strip()!=primary.model]
        for provider in candidates:
            key=provider.model
            with self.lock:
                status=self.health.setdefault(key,{'health':'not_checked','failures':0,'until':0})
                if status['until']>time.monotonic():
                    continue
            started=time.monotonic()
            try:
                result=provider.extract(statement,question_id,state)
                with self.lock:
                    self.health[key]={'health':'available','failures':0,'until':0,'latency_ms':int((time.monotonic()-started)*1000),'last_failure':None}
                return result,provider.name,None
            except (httpx.HTTPError,ValidationError,ValueError,RuntimeError) as exc:
                with self.lock:
                    failures=status['failures']+1
                    self.health[key]={'health':'cooldown','failures':failures,'until':time.monotonic()+min(300,5*2**min(failures,6)),'latency_ms':int((time.monotonic()-started)*1000),'last_failure':type(exc).__name__,'quota_status':'rate_limited' if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code==429 else 'not_reported'}
        fallback=RuleBasedProvider()
        return fallback.extract(statement,question_id,state),fallback.name,'AI unavailable; the structured clinical workflow is continuing with local rules.'


provider_manager=ProviderManager()


def safe_extract(statement: str, question_id: str, state: dict[str, Any]) -> tuple[StructuredExtraction, str, str | None]:
    return provider_manager.extract(statement,question_id,state)
