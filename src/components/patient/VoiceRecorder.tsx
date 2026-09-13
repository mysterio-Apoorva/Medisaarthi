'use client';

import React, { useRef, useState } from 'react';
import { Mic, Square } from 'lucide-react';

interface VoiceRecorderProps {
  onRecorded: (audio: Blob, filename: string) => Promise<void> | void;
  language?: 'hi' | 'en';
  isProcessing?: boolean;
}

/** A reusable recorder that returns actual microphone bytes; it never fabricates a transcript. */
export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({ onRecorded, language = 'hi', isProcessing = false }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const stopStream = () => { streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null; };

  const start = async () => {
    if (isProcessing || isRecording) return;
    setError(null); chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'].find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        stopStream(); setIsRecording(false);
        const actualType = recorder.mimeType || 'audio/webm';
        const audio = new Blob(chunksRef.current, { type: actualType });
        if (!audio.size) { setError(language === 'hi' ? 'रिकॉर्डिंग खाली है।' : 'The recording was empty.'); return; }
        const extension = actualType.includes('ogg') ? 'ogg' : actualType.includes('mp4') ? 'm4a' : 'webm';
        await onRecorded(audio, `patient_voice.${extension}`);
      };
      recorderRef.current = recorder;
      recorder.start(250);
      setIsRecording(true);
    } catch {
      stopStream();
      setError(language === 'hi' ? 'माइक्रोफ़ोन अनुमति नहीं मिली।' : 'Microphone permission was not granted.');
    }
  };

  const stop = () => { if (recorderRef.current?.state === 'recording') recorderRef.current.stop(); };

  return <div className="space-y-2">
    <button type="button" onClick={isRecording ? stop : start} disabled={isProcessing} className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-3 text-sm font-bold text-white disabled:opacity-50">
      {isRecording ? <Square className="h-4 w-4 fill-current" /> : <Mic className="h-4 w-4" />}
      {isRecording ? (language === 'hi' ? 'रोकें और भेजें' : 'Stop and send') : (language === 'hi' ? 'बोलकर बताएं' : 'Voice input')}
    </button>
    {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
  </div>;
};
