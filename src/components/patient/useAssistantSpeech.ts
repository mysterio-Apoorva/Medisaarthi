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
  const finish = useRef<((result: 'ended' | 'cancelled' | 'unavailable') => void) | null>(null);

  const stop = useCallback(() => {
    generation.current++;
    finish.current?.('cancelled'); finish.current = null;
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

  const unlock = useCallback(async () => {
    context.current ??= new AudioContext();
    if (context.current.state === 'running') return true;
    void context.current.resume().catch(() => undefined);
    await new Promise(resolve => setTimeout(resolve, 200));
    return (context.current?.state as AudioContextState) === 'running';
  }, []);

  const speak = useCallback(async (text: string, language: 'en' | 'hi'): Promise<'ended' | 'cancelled' | 'unavailable'> => {
    stop();
    if (!text.trim()) return 'ended';
    const ticket = generation.current;
    const controller = new AbortController();
    pending.current = controller;
    setNotice(null);
    setLoading(true);
    // Resume from the click gesture, before waiting for synthesis.
    try {
      await unlock();
    } catch { /* Browser speech fallback below. */ }
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      if (context.current?.state !== 'running') throw new Error('Playback requires activation');
      const response = await fetch(`${API_BASE_URL}/speech/synthesize`, {
        method: 'POST', credentials: 'include', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language }),
      });
      if (!response.ok) throw new Error(`Speech service returned ${response.status}`);
      const bytes = await response.arrayBuffer();
      const ctx = context.current;
      if (!ctx || ctx.state !== 'running') throw new Error('Audio playback requires a click');
      const decoded = await ctx.decodeAudioData(bytes);
      if (ticket !== generation.current) return 'cancelled';
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
      clearTimeout(timeout);
      const completion = new Promise<'ended' | 'cancelled' | 'unavailable'>(resolve => { finish.current = resolve; });
      node.onended = () => {
        if (ticket !== generation.current) return;
        cancelAnimationFrame(frame.current);
        node.disconnect(); analyser.disconnect(); source.current = null;
        setSpeaking(false); setMouth(0);
        finish.current?.('ended'); finish.current = null;
      };
      node.start();
      setSpeaking(true);
      setLoading(false);
      animate();
      return await completion;
    } catch {
      if (ticket !== generation.current) return 'cancelled';
      const synthesis = window.speechSynthesis;
      // Use only installed local voices; never silently send clinical text to a cloud voice.
      const voice = synthesis?.getVoices().find(v => v.localService && v.lang.startsWith(language));
      if (!synthesis || !voice || context.current?.state !== 'running') {
        setNotice(language === 'hi' ? 'आवाज़ उपलब्ध नहीं है। प्रश्न पढ़कर उत्तर दें या सुनें बटन फिर दबाएँ।' : 'Speech is unavailable. Read the question or click Listen to retry.');
        return 'unavailable';
      }
      setNotice(language === 'hi' ? 'डिवाइस की स्थानीय आवाज़ उपयोग हो रही है।' : 'Using your device’s local voice; mouth timing depends on browser speech events.');
      const utterance = new SpeechSynthesisUtterance(text);
      const completion = new Promise<'ended' | 'cancelled' | 'unavailable'>(resolve => { finish.current = resolve; });
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.onstart = () => { if (ticket === generation.current) setSpeaking(true); };
      utterance.onboundary = () => {
        if (ticket !== generation.current) return;
        setMouth(0.55);
        if (boundaryTimer.current) clearTimeout(boundaryTimer.current);
        boundaryTimer.current = setTimeout(() => setMouth(0), 130);
      };
      const watchdog = setTimeout(() => { if (ticket === generation.current) { synthesis.cancel(); finish.current?.('unavailable'); finish.current = null; } }, 90000);
      utterance.onend = () => {
        clearTimeout(watchdog);
        if (ticket === generation.current) { setSpeaking(false); setMouth(0); finish.current?.('ended'); finish.current = null; }
      };
      utterance.onerror = () => {
        clearTimeout(watchdog);
        if (ticket === generation.current) { setSpeaking(false); setMouth(0); finish.current?.('unavailable'); finish.current = null; }
      };
      setLoading(false);
      synthesis.speak(utterance);
      return await completion;
    } finally {
      clearTimeout(timeout);
      if (ticket === generation.current) setLoading(false);
    }
  }, [stop, unlock]);

  useEffect(() => () => {
    stop();
    void context.current?.close();
    context.current = null;
  }, [stop]);

  return { speaking, loading, mouth, notice, speak, stop, unlock };
}
