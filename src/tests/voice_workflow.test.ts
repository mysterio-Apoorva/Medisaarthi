import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const read = (relativePath: string) =>
  fs.readFileSync(path.resolve(process.cwd(), relativePath), 'utf-8');

describe('Voice client contract', () => {
  test('records real microphone bytes through MediaRecorder', () => {
    const page = read('src/app/patient/interview/page.tsx');
    assert.match(page, /navigator\.mediaDevices\.getUserMedia/);
    assert.match(page, /new MediaRecorder\(stream/);
    assert.match(page, /audio\/webm;codecs=opus/);
    assert.match(page, /id="voice-record-btn"/);
    assert.match(page, /id="voice-stop-btn"/);
    assert.match(page, /id="recording-indicator"/);
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
    assert.match(api, /\/interviews\/\$\{encodeURIComponent\(interviewId\)\}\/voice/);
    assert.match(api, /credentials: 'include'/);
    assert.doesNotMatch(api, /if \(!transcript\)/);
  });

  test('keeps failure, transcript, and typed-answer paths visible to the patient', () => {
    const page = read('src/app/patient/interview/page.tsx');
    assert.match(page, /Microphone access was not allowed/);
    assert.match(page, /id="processing-indicator"/);
    assert.match(page, /id="voice-transcript-card"/);
    assert.match(page, /id="voice-transcript-text"/);
    assert.match(page, /id="patient-answer-input"/);
    assert.match(page, /disabled=\{!inputText\.trim\(\) \|\| isSubmitting \|\| isProcessingVoice \|\| isRecording \|\| isRequestingMic\}/);
  });
});
