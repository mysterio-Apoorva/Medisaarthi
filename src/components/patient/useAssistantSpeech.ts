'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE_URL } from '@/services/api';

/** Mouth opening is measured from actual audio, never a looping talking animation. */
export function useAssistantSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mouth, setMouth] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const context = useRef<AudioContext | null>(null);
  const source = useRef<AudioBufferSourceNode | null>(null);
  const pending = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const frame = useRef(0);
  const boundaryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(() => {
    generation.current++;
    pending.current?.abort();
    pending.current = null;
    if (source.current) {
      source.current.onended = null;
      try { source.current.stop(); } catch { /* Already ended. */ }
      source.current.disconnect();
      source.current = null;
    }
    cancelAnimationFrame(frame.current);
    if (boundaryTimer.current) clearTimeout(boundaryTimer.current);
    window.speechSynthesis?.cancel();
    setSpeaking(false);
    setLoading(false);
    setMouth(0);
  }, []);

  const speak = useCallback(async (text: string, language: 'en' | 'hi') => {
    stop();
    if (!text.trim()) return;
    const ticket = generation.current;
    const controller = new AbortController();
    pending.current = controller;
    setNotice(null);
    setLoading(true);
    // Resume from the click gesture, before waiting for synthesis.
    try {
      context.current ??= new AudioContext();
      await context.current.resume();
    } catch { /* Browser speech fallback below. */ }
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(`${API_BASE_URL}/speech/synthesize`, {
        method: 'POST', credentials: 'include', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language }),
      });
      if (!response.ok) throw new Error(`Speech service returned ${response.status}`);
      const bytes = await response.arrayBuffer();
      const ctx = context.current;
      if (!ctx || ctx.state !== 'running') throw new Error('Audio playback requires a click');
      const decoded = await ctx.decodeAudioData(bytes);
      if (ticket !== generation.current) return;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      const node = ctx.createBufferSource();
      node.buffer = decoded;
      node.connect(analyser);
      analyser.connect(ctx.destination);
      source.current = node;
      const samples = new Uint8Array(analyser.fftSize);
      const animate = () => {
        if (ticket !== generation.current) return;
        analyser.getByteTimeDomainData(samples);
        const rms = Math.sqrt(samples.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / samples.length);
        setMouth(Math.min(1, Math.max(0, (rms - 0.008) * 7)));
        frame.current = requestAnimationFrame(animate);
      };
      node.onended = () => {
        if (ticket !== generation.current) return;
        cancelAnimationFrame(frame.current);
        node.disconnect(); analyser.disconnect(); source.current = null;
        setSpeaking(false); setMouth(0);
      };
      node.start();
      setSpeaking(true);
      animate();
    } catch {
      if (ticket !== generation.current) return;
      const synthesis = window.speechSynthesis;
      // Use only installed local voices; never silently send clinical text to a cloud voice.
      const voice = synthesis?.getVoices().find(v => v.localService && v.lang.startsWith(language));
      if (!synthesis || !voice) {
        setNotice(language === 'hi' ? 'आवाज़ उपलब्ध नहीं है। प्रश्न पढ़कर उत्तर दें या सुनें बटन फिर दबाएँ।' : 'Speech is unavailable. Read the question or click Listen to retry.');
        return;
      }
      setNotice(language === 'hi' ? 'डिवाइस की स्थानीय आवाज़ उपयोग हो रही है।' : 'Using your device’s local voice; mouth timing depends on browser speech events.');
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.onstart = () => { if (ticket === generation.current) setSpeaking(true); };
      utterance.onboundary = () => {
        if (ticket !== generation.current) return;
        setMouth(0.55);
        if (boundaryTimer.current) clearTimeout(boundaryTimer.current);
        boundaryTimer.current = setTimeout(() => setMouth(0), 130);
      };
      utterance.onend = utterance.onerror = () => {
        if (ticket === generation.current) { setSpeaking(false); setMouth(0); }
      };
      synthesis.speak(utterance);
    } finally {
      clearTimeout(timeout);
      if (ticket === generation.current) setLoading(false);
    }
  }, [stop]);

  useEffect(() => () => {
    stop();
    void context.current?.close();
    context.current = null;
  }, [stop]);

  return { speaking, loading, mouth, notice, speak, stop };
}
