# Hands-free patient interview

The interview route now presents the animated human SVG assistant as its main interface. It speaks the server's current question, listens automatically, waits for sustained silence, transcribes real microphone audio, and submits the answer through the existing authenticated clinical workflow. Review and submission consent remain explicit at the end.

## Running and browser activation

Start the API and Next.js as described in the root README, then sign in, select English or Hindi, and consent. The interview starts automatically where browser permissions allow. Otherwise use **Start** once and grant microphone permission. Browser autoplay policy cannot be bypassed by application code. There are no required Speak, Stop Recording, Submit Answer, or Next controls between successful voice turns.

Use **Pause**, **Help**, **Type instead**, or **Correct transcription** as needed. Correction is optional during the brief transcript preview; it cancels automatic submission while the patient edits. The review screen also allows correcting recorded clinical fields. Hiding the tab pauses the conversation and releases the microphone. A lost answer response is reconciled against the server revision before retrying.

## Audio and states

The controller explicitly tracks asking, speaking, listening, recording, transcribing, validating, processing, completion, pauses and microphone/transcription/speech/service errors. Speech resolves on playback completion, not on synthesis completion. Microphone capture begins after playback and a 450 ms echo tail. Barge-in is deliberately not enabled: this avoids the assistant recognizing its own voice.

Web Audio energy VAD uses RMS amplitude, an adaptive noise floor, speech-onset accumulation and sustained-silence hysteresis. An AudioWorklet captures actual mono PCM continuously on the audio thread. Independently decodable WAV chunks are transcribed during long answers without restarting the microphone; their transcripts form one clinical answer. The detector, not a fixed-duration timer, ends the utterance. Raw recordings are temporary server files and are removed after transcription.

Piper produces dynamic local speech. Web Audio playback amplitude drives the mouth. Installed local browser voices are a fallback with approximate boundary-based mouth timing. If neither voice works, the written question and typing remain available. Speech failure cannot silently advance a turn.

Whisper base remains the English default. Hindi uses the tested local Whisper small model with generic Devanagari script guidance. The script guidance contains no expected patient answers. Low-probability, repetitive, non-speech, empty and wrong-script Hindi results are rejected for retry. ASR is imperfect: the captured transcript remains visible and correctable.

## Configuration

Frontend variables are build-time `NEXT_PUBLIC_` settings. Restart the dev server/rebuild after changing them.

| Variable | Default | Meaning |
| --- | --- | --- |
| `NEXT_PUBLIC_VAD_ENABLED` | `true` | Enables automatic voice capture; false uses typing |
| `NEXT_PUBLIC_SILENCE_THRESHOLD` | `0.014` | Minimum normalized RMS speech threshold |
| `NEXT_PUBLIC_MIN_SPEECH_DURATION` | `220` | Accumulated speech milliseconds before accepting voice activity |
| `NEXT_PUBLIC_END_OF_SPEECH_DELAY` | `2800` | Sustained silence milliseconds before finishing an answer; minimum 2200 |
| `NEXT_PUBLIC_NO_SPEECH_TIMEOUT` | `18000` | Silence milliseconds before a gentle spoken prompt |
| `STT_MODEL` | `base` | English local Whisper model |
| `STT_MODEL_HI` | `small` | Hindi local Whisper model |
| `STT_MIN_AVG_LOGPROB` | `-1.0` | Reject less-confident transcription segments |
| `STT_MAX_NO_SPEECH_PROB` | `0.6` | Reject segments likely to contain no speech |

Existing Piper paths, Whisper device/cache configuration and Ollama provider settings still apply. There is no paid avatar, ASR or TTS API. The first use downloads missing Whisper weights; cache the models before an offline demonstration. English/Hindi are the configured product languages. Hinglish can be spoken in Hindi mode; additional languages need appropriate ASR, TTS and UI translations and are not advertised as installed.

## Clinical budget and safety

`backend/app/question_budget.py` owns a hard minimum of five and maximum of ten completed clinical questions. The answer rows are authoritative: refreshes, fact corrections and failed transcription attempts do not spend questions. An additive database migration stores the current question, including the fields it covers and any document confirmation source, so a response is interpreted against the actual question shown.

The engine groups missing symptom details, screens safety early, and prioritizes relevant history. A simple case can finish at five; unresolved information can use up to ten. At ten, uncollected facts remain missing for clinician review. Neither patient corrections nor submission can trigger an eleventh question. The review screen permits submission at the budget limit with explicit missing-information disclosure; clinician finalization still requires critical fields to be addressed.

Deterministic red flags are evaluated before waiting for a language model. A flag interrupts normal speaking/listening with a safety message and pause. A patient or helper can resume once help is present. This is a safety pause, not an early completed interview. No staff message or emergency call is sent automatically. Conflicting newly reported danger stays visible pending clinical review, including in the doctor's queue.

Prior document entities and verified historical facts are used as confirmation candidates. Unverified OCR is never silently treated as current medication/allergy history. An explicit confirmation writes a patient-reported fact with the document reference and creates the normal timeline event; the original source and clinician reconciliation remain available. A bare rejection of an old prescription does not assert that the patient takes no medicines.

The LLM can extract several allowed fields from one answer, but it cannot control the question budget or invent values from a previous answer. The existing clinical facts, timeline, audit, doctor summary, document reconciliation, follow-up and FHIR paths remain in use.

## Verification

```powershell
npm run test:vad
npm run test:handsfree
npm run test:browser
npm run test:unit
npm run lint
```

The hands-free harness substitutes synthetic Piper patient PCM for the physical microphone source, then exercises the real AudioWorklet, WAV upload, Whisper, clinical API, local model and Piper playback. It does not mock transcripts or server responses. The 12 scenarios cover normal five-question completion with a two-second internal pause, silence, rejected tone/no-speech audio, a long response, ten unknown answers, red flags, denied microphone permission, Hindi, document confirmation, correction, autoplay recovery and correction after a dropped request. Permission and autoplay failures are explicit browser fault injections; the dropped-request scenario aborts one connection and retries against the real API. Headless Edge allowed autoplay under its native policy during these runs, so the injected restriction checks the otherwise unexercised Start recovery path.

Evidence and screenshots are generated under `backend/data/handsfree-e2e/`. The separate browser integration test exercises typing, refresh persistence, PDF extraction, review consent, clinician reconciliation, FHIR download, finalization and administrator audit. Unit tests cover the budget, source confirmation, missing data, grounded multi-field extraction, safety and existing clinical workflows. The VAD test also verifies 104 seconds of continuous PCM with no dropped or reordered samples.

These automated runs do not certify a physical hospital microphone, room acoustics, accents, speakers or every browser. Energy VAD may need threshold adjustment in a noisy kiosk. Reduced-motion preferences disable idle/head/blink animation while preserving the speech cue.

Implementation references: [Web Audio media streams](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/createMediaStreamSource), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), and the installed Next.js development-origin/client-component guides.
