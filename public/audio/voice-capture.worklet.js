/* global AudioWorkletProcessor, registerProcessor */
// Capture on the audio thread. The UI never gates or drops PCM while ASR is busy.
class PatientAudioCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(512);
    this.used = 0;
    this.port.onmessage = event => {
      if (event.data === 'flush') { this.flush(); this.port.postMessage({ done: true }); }
    };
  }
  flush() {
    if (!this.used) return;
    const pcm = this.buffer.slice(0, this.used);
    this.port.postMessage({ pcm }, [pcm.buffer]);
    this.used = 0;
  }
  process(inputs) {
    const samples = inputs[0]?.[0];
    if (samples) for (const value of samples) {
      this.buffer[this.used++] = value;
      if (this.used === this.buffer.length) this.flush();
    }
    // Output remains zero: microphone audio is never played through the speakers.
    return true;
  }
}
registerProcessor('patient-audio-capture', PatientAudioCapture);
