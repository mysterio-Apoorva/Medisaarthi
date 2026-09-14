/** Central VAD configuration: milliseconds and normalized RMS amplitude. */
function setting(value: string | undefined, fallback: number, min: number, max: number) {
  const parsed = Number(value);
  return value && Number.isFinite(parsed) ? Math.max(min, Math.min(max, parsed)) : fallback;
}
export const voiceConfig = {
  enabled: process.env.NEXT_PUBLIC_VAD_ENABLED !== 'false',
  silenceThreshold: setting(process.env.NEXT_PUBLIC_SILENCE_THRESHOLD, .014, .002, .2),
  minSpeechMs: setting(process.env.NEXT_PUBLIC_MIN_SPEECH_DURATION, 220, 100, 1500),
  endOfSpeechMs: setting(process.env.NEXT_PUBLIC_END_OF_SPEECH_DELAY, 2800, 2200, 8000),
  noSpeechMs: setting(process.env.NEXT_PUBLIC_NO_SPEECH_TIMEOUT, 18000, 8000, 60000),
  chunkMs: 100000,
  echoTailMs: 450,
  sampleMs: 30,
};
export type VadEvent = 'waiting' | 'speech' | 'end' | 'silence';

/** Energy VAD with noise adaptation, attack accumulation and pause hysteresis. */
export class VoiceActivityDetector {
  private speechMs = 0;
  private lastVoice = 0;
  private lastSample: number;
  private started: number;
  private floor = .003;
  speaking = false;
  constructor(private config = voiceConfig, now = 0) { this.started = this.lastSample = now; }
  sample(rms: number, now: number): VadEvent {
    const dt = Math.min(100, Math.max(0, now - this.lastSample)); this.lastSample = now;
    const threshold = Math.max(this.config.silenceThreshold, Math.min(.07, this.floor * 3));
    const voiced = rms > threshold;
    if (!voiced && !this.speaking) this.floor = this.floor * .98 + rms * .02;
    if (voiced) {
      this.speechMs += dt; this.lastVoice = now;
      if (this.speechMs >= this.config.minSpeechMs) this.speaking = true;
    } else if (!this.speaking) this.speechMs = Math.max(0, this.speechMs - dt / 2);
    if (this.speaking && now - this.lastVoice >= this.config.endOfSpeechMs) return 'end';
    if (!this.speaking && now - this.started >= this.config.noSpeechMs) return 'silence';
    return this.speaking ? 'speech' : 'waiting';
  }
}

export type CaptureResult = { kind: 'answer'; audio: Blob; filename: string } | { kind: 'silence' | 'cancelled' };
type AudioChunk = { audio: Blob; filename: string };

/** PCM WAV chunks are independently decodable; there are no missing WebM headers. */
function wav(chunks: Float32Array[], rate: number): Blob {
  const length = chunks.reduce((n, c) => n + c.length, 0);
  const buffer = new ArrayBuffer(44 + length * 2); const view = new DataView(buffer);
  const text = (offset: number, value: string) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
  text(0, 'RIFF'); view.setUint32(4, 36 + length * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, length * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const sample of chunk) {
    view.setInt16(offset, Math.round(Math.max(-1, Math.min(1, sample)) * 32767), true); offset += 2;
  }
  return new Blob([buffer], { type: 'audio/wav' });
}

/** Continuous audio-thread capture. ASR of a long-answer chunk never stops the mic. */
export class VoiceCapture {
  async listen(signal: AbortSignal, onSpeech: () => void, onLevel: (level: number) => void, onChunk: (chunk: AudioChunk) => void): Promise<CaptureResult> {
    if (!voiceConfig.enabled) throw new Error('Voice input is disabled');
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone unavailable');
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
    if (signal.aborted) { stream.getTracks().forEach(t => t.stop()); return { kind: 'cancelled' }; }
    const ctx = new AudioContext({ sampleRate: 16000 });
    let cancel: (() => void) | undefined;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    let node: AudioWorkletNode | undefined;
    try {
      void ctx.resume();
      await new Promise(resolve => setTimeout(resolve, 200));
      if (ctx.state !== 'running') throw new Error('Microphone audio needs activation');
      await ctx.audioWorklet.addModule('/audio/voice-capture.worklet.js');
      if (signal.aborted) return { kind: 'cancelled' };
      const input = ctx.createMediaStreamSource(stream);
      const filter = ctx.createBiquadFilter(); filter.type = 'highpass'; filter.frequency.value = 100;
      node = new AudioWorkletNode(ctx, 'patient-audio-capture');
      const processor = node;
      input.connect(filter); filter.connect(processor); processor.connect(ctx.destination);
      return await new Promise<CaptureResult>((resolve, reject) => {
        let chunks: Float32Array[] = []; let sampleCount = 0;
        const started = performance.now(); const detector = new VoiceActivityDetector(voiceConfig, started);
        let voiced = false; let ending: 'answer' | 'silence' | null = null;
        const chunk = () => ({ audio: wav(chunks, ctx.sampleRate), filename: 'answer.wav' });
        cancel = () => resolve({ kind: 'cancelled' });
        signal.addEventListener('abort', cancel, { once: true });
        if (signal.aborted) { cancel(); return; }
        const heartbeat = () => {
          clearTimeout(watchdog);
          watchdog = setTimeout(() => reject(new Error('Microphone stopped providing audio')), 5000);
        };
        heartbeat();
        processor.onprocessorerror = () => reject(new Error('Microphone audio processing failed'));
        stream.getAudioTracks().forEach(track => { track.onended = () => { if (!signal.aborted) reject(new Error('Microphone disconnected')); }; });
        processor.port.onmessage = event => {
          if (signal.aborted) return;
          heartbeat();
          if (event.data.done) {
            if (ending === 'answer') resolve({ kind: 'answer', ...chunk() });
            else resolve({ kind: 'silence' });
            return;
          }
          const pcm = event.data.pcm as Float32Array;
          chunks.push(pcm); sampleCount += pcm.length;
          if (ending) return;
          const rms = Math.sqrt(pcm.reduce((sum, v) => sum + v * v, 0) / pcm.length);
          onLevel(Math.min(1, rms * 12));
          const activity = detector.sample(rms, performance.now());
          if (activity === 'speech' && !voiced) { voiced = true; onSpeech(); }
          if (activity === 'end' || activity === 'silence') {
            ending = activity === 'end' ? 'answer' : 'silence'; processor.port.postMessage('flush');
          } else if (sampleCount >= ctx.sampleRate * voiceConfig.chunkMs / 1000) {
            onChunk(chunk()); chunks = []; sampleCount = 0;
          }
        };
      });
    } finally {
      if (cancel) signal.removeEventListener('abort', cancel);
      clearTimeout(watchdog);
      if (node) { node.port.onmessage = null; node.disconnect(); }
      stream.getTracks().forEach(t => { t.onended = null; t.stop(); });
      await ctx.close(); onLevel(0);
    }
  }
}
