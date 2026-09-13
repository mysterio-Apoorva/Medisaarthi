"""Optional guideline retrieval boundary. It never stores or retrieves patient records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuidelineSource:
    source_id: str
    title: str
    text: str
    provenance: str


class GuidelineRetriever:
    """A dependency-free lexical fallback; deploy pgvector/Ollama embeddings for scale."""
    def __init__(self, sources: list[GuidelineSource] | None = None) -> None:
        self.sources = sources or []

    def retrieve(self, query: str, limit: int = 3) -> list[GuidelineSource]:
        terms = {term.casefold() for term in query.split() if len(term) > 2}
        ranked = sorted(self.sources, key=lambda source: len(terms & set(source.text.casefold().split())), reverse=True)
        return [source for source in ranked[:limit] if terms & set(source.text.casefold().split())]
