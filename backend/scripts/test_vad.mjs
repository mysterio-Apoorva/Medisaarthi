// Exercise the shipped TypeScript detector, with measured-amplitude sample sequences.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = ts.transpileModule(readFileSync('src/lib/voice-activity.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const context = { exports: {}, process: { env: {} } };
vm.runInNewContext(source, context);
const { VoiceActivityDetector, voiceConfig } = context.exports;
function run(sections) {
  const detector = new VoiceActivityDetector(voiceConfig, 0);
  let time = 0; const events = [];
  for (const [ms, level] of sections) {
    let result;
    for (let i = 0; i < ms; i += 30) { time += 30; result = detector.sample(level, time); }
    events.push(result);
  }
  return events;
}
assert.deepEqual(run([[600,.09],[2010,0],[600,.09],[2700,0],[150,0]]), ['speech','speech','speech','speech','end']);
assert.deepEqual(run([[300,.09],[2850,0]]), ['speech','end']); // A short 'no' is retained.
assert.deepEqual(run([[18030,0]]), ['silence']);
assert.deepEqual(run([[90,.1],[1000,0]]), ['waiting','waiting']); // Clicks do not count.
assert.deepEqual(run([[1000,.006],[600,.09],[2850,.006]]), ['waiting','speech','end']);
assert.deepEqual(run([[90000,.09],[2850,0]]), ['speech','end']);
console.log('PASS: 2-second pauses, short answers, silence, clicks, background noise, long speech');

// Audio-thread continuity across more than one 100-second ASR chunk.
let Processor; const captured = [];
class WorkletBase {
  constructor() { this.port = { postMessage: message => { if (message.pcm) captured.push(message.pcm); }, onmessage: null }; }
}
vm.runInNewContext(readFileSync('public/audio/voice-capture.worklet.js', 'utf8'), {
  AudioWorkletProcessor: WorkletBase, registerProcessor: (_, implementation) => { Processor = implementation; },
});
const worklet = new Processor(); let sent = 0;
for (let i = 0; i < 13000; i++) {
  const samples = Float32Array.from({ length: 128 }, (_, n) => ((sent + n) % 100) / 100);
  sent += samples.length; worklet.process([[samples]]);
}
worklet.port.onmessage({ data: 'flush' });
assert.equal(captured.reduce((n, c) => n + c.length, 0), sent);
let checked = 0;
for (const chunk of captured) for (const sample of chunk) assert.equal(sample, Math.fround((checked++ % 100) / 100));
console.log('PASS: 104 seconds of continuous PCM retained without loss or reordering');
