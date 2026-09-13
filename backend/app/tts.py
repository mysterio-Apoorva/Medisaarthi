"""Local Piper speech; generated WAV bytes never leave this server for inference."""
from __future__ import annotations

import io
import os
import wave
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from typing import Literal
from backend.app.security import AuthenticatedUser, current_user

router = APIRouter(prefix="/speech", tags=["Local speech"])
_voices: dict = {}
_lock = Lock()


class SpeechInput(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    language: Literal["en", "hi"] = "en"


def synthesize(text: str, language: str) -> bytes:
    name = "hi_IN-pratham-medium" if language == "hi" else "en_US-lessac-medium"
    path = Path(os.getenv(f"TTS_MODEL_{language.upper()}", f"backend/data/tts/{name}.onnx")).resolve()
    if not path.is_file():
        raise RuntimeError("Local voice is not installed")
    from piper import PiperVoice
    with _lock:
        voice = _voices.get(str(path))
        if voice is None:
            voice = PiperVoice.load(str(path))
            _voices[str(path)] = voice
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            voice.synthesize_wav(text, wav)
        return output.getvalue()


@router.post("/synthesize")
def speech(payload: SpeechInput, user: AuthenticatedUser = Depends(current_user)):
    if not payload.text.strip():
        raise HTTPException(422, "Speech text cannot be blank")
    try:
        content = synthesize(payload.text.strip(), payload.language)
    except Exception as exc:
        raise HTTPException(503, "Local voice unavailable. Use your browser voice or read the question.") from exc
    return Response(content, media_type="audio/wav", headers={"Cache-Control": "no-store", "X-Speech-Provider": "piper"})
