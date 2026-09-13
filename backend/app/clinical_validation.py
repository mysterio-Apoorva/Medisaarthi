"""Field semantics shared by patient corrections and clinician review."""
from typing import Any
from fastapi import HTTPException
from backend.app.clinical_engine import ADDITIONAL_DOCUMENT_FIELDS, AYUSH_FIELDS, BOOL_FIELDS, LIST_FIELDS, QUESTIONS


def validate_fact(field: str, value: Any) -> Any:
    if field not in set(QUESTIONS) | set(AYUSH_FIELDS) | BOOL_FIELDS | LIST_FIELDS | ADDITIONAL_DOCUMENT_FIELDS:
        raise HTTPException(422, 'Unknown clinical field')
    if field in BOOL_FIELDS:
        valid = type(value) is bool
    elif field in LIST_FIELDS | ADDITIONAL_DOCUMENT_FIELDS:
        valid = isinstance(value, list) and len(value) <= 50 and all(isinstance(v, str) and 0 < len(v.strip()) <= 500 for v in value)
    elif field == 'severity':
        # Legacy doctor UI submits numeric text; accept an exact integer, not qualitative guesses.
        if isinstance(value, str) and value.strip().isdigit():
            value = int(value.strip())
        valid = type(value) is int and 0 <= value <= 10
    else:
        valid = isinstance(value, str) and 0 < len(value.strip()) <= (4000 if field in AYUSH_FIELDS else 2000)
    if not valid:
        raise HTTPException(422, 'Invalid value for this clinical field')
    return value
