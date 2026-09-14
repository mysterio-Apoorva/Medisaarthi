import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const read = (relativePath: string) =>
  fs.readFileSync(path.resolve(process.cwd(), relativePath), 'utf-8');

describe('Voice client contract', () => {
  test('captures real microphone PCM continuously on the audio thread', () => {
    const capture = read('src/lib/voice-activity.ts');
    assert.match(capture, /navigator\.mediaDevices\.getUserMedia/);
    assert.match(capture, /new AudioWorkletNode/);
    assert.match(capture, /audio\/wav/);
    assert.match(capture, /onChunk\(chunk\(\)\)/);
  });

  test('does not use browser recognition or simulated transcripts', () => {
    const page = read('src/app/patient/interview/page.tsx');
    const recorder = read('src/components/patient/VoiceRecorder.tsx');
    for (const content of [page, recorder]) {
      assert.doesNotMatch(content, /SpeechRecognition|webkitSpeechRecognition|sampleTranscriptions|setTimeout\([^)]*transcript/i);
    }
  });

  test('sends the recorded Blob to the authenticated multipart voice API', () => {
    const api = read('src/services/api.ts');
    assert.match(api, /form\.append\('file', audio, filename\)/);
    assert.match(api, /form\.append\('expected_revision'/);
    assert.match(api, /\/interviews\/\$\{encodeURIComponent\(id\)\}\/transcribe/);
    assert.match(api, /credentials: 'include'/);
    assert.doesNotMatch(api, /if \(!transcript\)/);
  });

  test('keeps failure, transcript, and typed-answer paths visible to the patient', () => {
    const page = read('src/app/patient/interview/page.tsx');
    assert.match(page, /MICROPHONE_ERROR/);
    assert.match(page, /TRANSCRIPTION_ERROR/);
    assert.match(page, /data-testid="last-transcript"/);
    assert.match(page, /Correct transcription/);
    assert.match(page, /id="patient-answer-input"/);
    assert.match(page, /submitting\.current/);
    assert.doesNotMatch(page, /id="voice-record-btn"|id="voice-stop-btn"/);
  });
});
