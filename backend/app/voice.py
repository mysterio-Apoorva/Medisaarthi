"""Local, privacy-preserving speech-to-text for patient audio uploads."""

from __future__ import annotations

import os
import math
import re
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool


MAX_AUDIO_BYTES = 15 * 1024 * 1024
_ALLOWED_AUDIO = {
    "audio/webm": (".webm", b"\x1aE\xdf\xa3"),
    "audio/ogg": (".ogg", b"OggS"),
    "audio/wav": (".wav", b"RIFF"),
    "audio/mp4": (".m4a", b""),
}
_models: dict[str, Any] = {}
_model_lock = Lock()


class SpeechToTextUnavailable(RuntimeError):
    """Raised when the optional local Whisper runtime/model cannot be loaded."""


def _get_model(language: str = 'en'):
    name = os.getenv('STT_MODEL_HI', 'small') if language == 'hi' else os.getenv('STT_MODEL', 'base')
    if name in _models:
        return _models[name]
    with _model_lock:
        if name in _models:
            return _models[name]
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SpeechToTextUnavailable("The local speech recognition runtime is not installed") from exc
        try:
            _models[name] = WhisperModel(
                name,
                device=os.getenv("STT_DEVICE", "cpu"),
                compute_type=os.getenv("STT_COMPUTE_TYPE", "int8"),
                download_root=os.getenv("STT_MODEL_DIR", "backend/data/models"),
            )
        except Exception as exc:
            raise SpeechToTextUnavailable("The local speech model could not be loaded") from exc
    return _models[name]


async def transcribe_upload(upload: UploadFile, language: str) -> str:
    """Validate, temporarily store, locally transcribe, then securely remove audio."""
    content_type = (upload.content_type or "").split(";", 1)[0].casefold()
    accepted = _ALLOWED_AUDIO.get(content_type)
    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only WebM, Ogg, WAV, and M4A microphone recordings are accepted",
        )
    payload = await upload.read(MAX_AUDIO_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The microphone recording is empty")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The microphone recording exceeds the 15 MB limit")
    suffix, signature = accepted
    if signature and not payload.startswith(signature):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="The audio file header does not match its declared format")
    if content_type == "audio/wav" and payload[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The WAV recording has an invalid header")
    if content_type == "audio/mp4" and b"ftyp" not in payload[:64]:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="The audio file header does not match its declared format")

    return await run_in_threadpool(_transcribe_bytes, payload, suffix, language)


def _transcribe_bytes(payload: bytes, suffix: str, language: str) -> str:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        try:
            from faster_whisper.audio import decode_audio
            samples = decode_audio(str(temp_path), sampling_rate=16000)
            if len(samples) > 16000 * 120:
                raise HTTPException(status_code=413, detail="Please record at most two minutes at a time")
            segments, _ = _get_model(language).transcribe(
                samples,
                language="hi" if language == "hi" else "en",
                vad_filter=True,
                beam_size=5,
                condition_on_previous_text=False,
                # Script guidance contains no expected symptoms or answers.
                initial_prompt='नमस्ते। यह हिंदी देवनागरी लिपि है।' if language == 'hi' else None,
            )
            segments = list(segments)
            min_logprob = float(os.getenv('STT_MIN_AVG_LOGPROB', '-1.0'))
            max_no_speech = float(os.getenv('STT_MAX_NO_SPEECH_PROB', '0.6'))
            # Reject the whole utterance if part is unintelligible; never silently omit
            # a low-confidence negation, medicine or number and submit the remainder.
            if any(not math.isfinite(s.avg_logprob) or s.avg_logprob < min_logprob
                   or s.no_speech_prob > max_no_speech or s.compression_ratio > 2.4 for s in segments):
                raise HTTPException(status_code=422, detail='Speech was unclear. Please say your answer again.')
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
        except SpeechToTextUnavailable:
            raise
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The recording could not be transcribed. Please speak clearly and try again.") from exc
        if not transcript or not re.search(r'[^\W_]', transcript, re.UNICODE):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No intelligible speech was found in the recording")
        if language == 'hi' and re.search(r'[\u0600-\u06ff]', transcript):
            raise HTTPException(422, 'The speech language was unclear. Please repeat your answer.')
        return transcript
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
