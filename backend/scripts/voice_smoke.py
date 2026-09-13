"""Verify the real local microphone pipeline with a supplied WAV recording.

The speech fixture is deliberately supplied by the caller; this script never
pretends a particular transcript was recorded.  Presentation tests can add
expected words for their own recorded chest-pain fixture.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.main import app


def expect(response, status_code: int):
    assert response.status_code == status_code, response.text
    return response.json()


def main(audio_path: Path, expected_terms: tuple[str, ...] = ()) -> None:
    assert audio_path.is_file() and audio_path.stat().st_size > 44, "Provide a non-empty WAV speech recording"
    with TestClient(app) as client:
        expect(client.post("/auth/login", json={"email": "patient.demo@medikiosk.local", "password": "DemoPass!2026"}), 200)
        consent = expect(client.post("/interviews/consents", json={"patient_id": "P1001", "consent_type": "CLINICAL_INTAKE"}), 201)
        started = expect(client.post("/interviews/start", json={"patient_id": "P1001", "language": "en", "consent_id": consent["consent_id"]}), 201)
        with audio_path.open("rb") as audio:
            response = expect(
                client.post(
                    f"/interviews/{started['encounter_id']}/voice",
                    data={"expected_revision": str(started["revision"])},
                    files={"file": ("local-speech.wav", audio, "audio/wav")},
                ),
                200,
            )
        transcript = response["transcript"].casefold()
        assert transcript, response
        for term in expected_terms:
            assert term.casefold() in transcript, transcript
        assert response["clinical_state"].get("chief_complaint"), response
        assert response["stt_provider"] == "faster_whisper"
    print(f"Voice smoke passed: server transcript = {response['transcript']!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_path", type=Path, help="A real spoken WAV recording")
    parser.add_argument("--expect", action="append", default=[], help="Case-insensitive word expected in this recording; repeat as needed")
    args = parser.parse_args()
    main(args.audio_path, tuple(args.expect))
