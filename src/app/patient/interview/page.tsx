'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, Check, HelpCircle, Keyboard, Mic, Pause, Play, X } from 'lucide-react';
import { getIntakeSnapshot, sendIntakeAnswer, startInterviewSession, transcribeInterviewAudio, ApiError, type IntakeSnapshot } from '@/services/api';
import { TalkingAvatar } from '@/components/patient/TalkingAvatar';
import { useAssistantSpeech } from '@/components/patient/useAssistantSpeech';
import { VoiceCapture, voiceConfig } from '@/lib/voice-activity';

type ConversationState = 'IDLE' | 'ASKING' | 'SPEAKING' | 'LISTENING' | 'RECORDING' | 'TRANSCRIBING' | 'PROCESSING' | 'VALIDATING' | 'NEXT_QUESTION' | 'COMPLETED' | 'PAUSED' | 'SAFETY_PAUSE' | 'TRANSCRIPTION_ERROR' | 'AI_ERROR' | 'TTS_ERROR' | 'MICROPHONE_ERROR';
const LABELS: Record<ConversationState, [string, string]> = {
  IDLE: ['Getting ready', 'तैयार हो रहे हैं'], ASKING: ['One moment', 'एक क्षण'],
  SPEAKING: ['Your assistant is speaking', 'आपका सहायक बोल रहा है'],
  LISTENING: ['Listening · take your time', 'सुन रहे हैं · आराम से बोलिए'],
  RECORDING: ['Listening to you', 'आपकी बात सुन रहे हैं'],
  TRANSCRIBING: ['Understanding your words', 'आपकी बात समझ रहे हैं'],
  PROCESSING: ['Understanding your answer', 'आपका उत्तर समझ रहे हैं'],
  VALIDATING: ['Checking what you shared', 'आपकी बात देख रहे हैं'],
  NEXT_QUESTION: ['One moment', 'एक क्षण'], COMPLETED: ['Thank you', 'धन्यवाद'],
  PAUSED: ['Take your time', 'आराम से समय लीजिए'], SAFETY_PAUSE: ['Please ask a member of staff for help', 'कृपया अस्पताल के कर्मचारी से मदद माँगें'],
  TRANSCRIPTION_ERROR: ['Let’s try that again', 'फिर से कोशिश करते हैं'],
  AI_ERROR: ['Your answer needs another moment', 'आपके उत्तर के लिए थोड़ा और समय चाहिए'],
  TTS_ERROR: ['Let’s enable your assistant’s voice', 'सहायक की आवाज़ शुरू करें'],
  MICROPHONE_ERROR: ['We need access to your microphone', 'माइक्रोफ़ोन की अनुमति चाहिए'],
};
function delay(ms: number, signal: AbortSignal) {
  return new Promise<void>(resolve => {
    const done = () => { clearTimeout(timer); signal.removeEventListener('abort', done); resolve(); };
    const timer = setTimeout(done, ms); signal.addEventListener('abort', done, { once: true });
    if (signal.aborted) done();
  });
}

export default function PatientInterviewPage() {
  const router = useRouter();
  const [snapshot, setSnapshot] = useState<IntakeSnapshot | null>(null);
  const [phase, setPhase] = useState<ConversationState>('IDLE');
  const [paused, setPaused] = useState(false);
  const [typing, setTyping] = useState(!voiceConfig.enabled);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [lastTranscript, setLastTranscript] = useState('');
  const [spokenText, setSpokenText] = useState('');
  const [error, setError] = useState('');
  const [help, setHelp] = useState(false);
  const [level, setLevel] = useState(0);
  const [acknowledged, setAcknowledged] = useState('');
  const [retry, setRetry] = useState(0);
  const speech = useAssistantSpeech();
  const { speak, stop, unlock } = speech;
  const active = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const hi = snapshot?.language === 'hi';
  const language = snapshot?.language || 'en';
  const safetyKey = snapshot?.priority_flags.map(f => f.code).sort().join('|') || '';
  const completed = !!snapshot && snapshot.status !== 'ACTIVE';
  const interrupt = useCallback(() => { active.current?.abort(); stop(); }, [stop]);

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      try {
        const patient = localStorage.getItem('medisaarthi_current_patient_id');
        const consent = localStorage.getItem('medisaarthi_current_consent_id');
        if (!patient || !consent) { router.replace(!patient ? '/patient/identify' : '/patient/consent'); return; }
        const lang = localStorage.getItem('medisaarthi_selected_lang') === 'en' ? 'en' : 'hi';
        const mode = localStorage.getItem('medisaarthi_care_mode') === 'AYUSH' ? 'AYUSH' : 'MODERN';
        const start = await startInterviewSession(patient, lang, consent, mode);
        const current = await getIntakeSnapshot(start.interview_id);
        if (cancelled) return;
        localStorage.setItem('medisaarthi_current_interview_id', start.interview_id);
        setSnapshot(current);
      } catch (err) {
        if (!cancelled) { setError(err instanceof Error ? err.message : 'Unable to load your interview.'); setPhase('AI_ERROR'); }
      }
    }
    void initialize();
    return () => { cancelled = true; interrupt(); };
  }, [router, interrupt]);

  useEffect(() => {
    const pauseOnHidden = () => { if (document.hidden) { interrupt(); setPaused(true); } };
    document.addEventListener('visibilitychange', pauseOnHidden);
    return () => document.removeEventListener('visibilitychange', pauseOnHidden);
  }, [interrupt]);

  useEffect(() => {
    if (!snapshot || paused || typing || editing) return;
    const controller = new AbortController(); active.current = controller;
    const signal = controller.signal;
    const current = snapshot;
    const isHindi = current.language === 'hi';
    const say = async (text: string) => {
      if (signal.aborted) return false;
      setSpokenText(text); setPhase('ASKING');
      const result = await speak(text, current.language);
      if (signal.aborted || result === 'cancelled') return false;
      if (result === 'unavailable') {
        setPhase('TTS_ERROR'); setPaused(true);
        setError(isHindi ? 'आवाज़ चालू करने के लिए शुरू करें दबाएँ। आप लिख भी सकते हैं।' : 'Tap Start to enable sound. You can also type your answer.');
        return false;
      }
      await delay(voiceConfig.echoTailMs, signal);
      return !signal.aborted;
    };
    async function runTurn() {
      setError('');
      if (safetyKey && safetyKey !== acknowledged) {
        const message = isHindi
          ? 'आपकी बताई तकलीफ के लिए तुरंत स्वास्थ्य कर्मचारी की मदद ज़रूरी है। कृपया अभी कर्मचारी को बुलाएँ। हम बातचीत रोक रहे हैं।'
          : 'What you have described needs prompt attention from a healthcare professional. Please ask a member of staff for help now. We will pause here.';
        await say(message);
        if (!signal.aborted) setPhase('SAFETY_PAUSE');
        return;
      }
      if (current.status !== 'ACTIVE') {
        const message = isHindi ? 'धन्यवाद। आपकी बताई जानकारी डॉक्टर की समीक्षा के लिए एकत्र हो गई है। अब आप इसे देख सकते हैं।'
          : 'Thank you. I have collected what you shared for your doctor to review. You can now check your information.';
        if (await say(message)) {
          setPhase('COMPLETED');
          await delay(2500, signal);
          if (!signal.aborted) router.push('/patient/review');
        }
        return;
      }
      if (!current.next_question || !await say(current.next_question.text)) return;
      const capture = new VoiceCapture();
      let attempts = 0;
      const parts: Promise<string>[] = [];
      while (!signal.aborted) {
        setPhase('LISTENING');
        let recording;
        try { recording = await capture.listen(signal, () => setPhase('RECORDING'), setLevel, chunk => {
          const transcription = transcribeInterviewAudio(current.interview_id, chunk.audio, chunk.filename, current.revision, signal).then(result => result.transcript);
          void transcription.catch(() => undefined);
          parts.push(transcription);
        }); }
        catch {
          if (!signal.aborted) {
            setPhase('MICROPHONE_ERROR'); setPaused(true);
            setError(isHindi ? 'माइक्रोफ़ोन की अनुमति दें और फिर शुरू करें। या लिखकर उत्तर दें।' : 'Allow microphone access and press Start again, or type your answer.');
          }
          return;
        }
        if (signal.aborted || recording.kind === 'cancelled') return;
        if (recording.kind === 'silence' && !parts.length) {
          if (!await say(isHindi ? 'आराम से बोलिए। जब आप तैयार हों, अपनी बात बताइए।' : 'Take your time. Whenever you are ready, you can tell me.')) return;
          continue;
        }
        if ('audio' in recording) {
          // Long responses transcribe completed chunks while capture continues. No turn is spent yet.
          const chunk = transcribeInterviewAudio(current.interview_id, recording.audio, recording.filename, current.revision, signal)
            .then(result => result.transcript);
          void chunk.catch(() => undefined);
          parts.push(chunk);
        }
        setPhase('TRANSCRIBING');
        try {
          const transcript = (await Promise.all(parts)).join(' ').trim(); parts.length = 0;
          if (signal.aborted) return;
          if (!transcript || !/[\p{L}\p{N}]/u.test(transcript)) throw new Error('Unclear speech');
          setLastTranscript(transcript); setDraft(transcript); setPhase('VALIDATING');
          // Optional correction; the ordinary conversation never waits for a button.
          await delay(2200, signal);
          if (signal.aborted) return;
          setPhase('PROCESSING'); submitting.current = true;
          try {
            const next = await sendIntakeAnswer(current.interview_id, transcript, current.revision, signal);
            if (!signal.aborted) { setDraft(''); setPhase('NEXT_QUESTION'); setSnapshot(next); }
          } catch {
            if (!signal.aborted) {
              // A timed-out response may already be saved; reconcile before offering any retry.
              const latest = await getIntakeSnapshot(current.interview_id).catch(() => null);
              if (signal.aborted) return;
              if (latest && latest.revision !== current.revision) { setSnapshot(latest); setDraft(''); }
              else { setError(isHindi ? 'उत्तर सुरक्षित नहीं हुआ। इसे नीचे देखकर फिर भेजें।' : 'Your answer was not saved. Please review it below and try again.'); setEditing(true); setPhase('AI_ERROR'); }
            }
          } finally { submitting.current = false; }
          return;
        } catch (err) {
          parts.length = 0;
          if (signal.aborted) return;
          if (err instanceof ApiError && err.status === 409) { setSnapshot(await getIntakeSnapshot(current.interview_id)); return; }
          setPhase('TRANSCRIPTION_ERROR'); attempts++;
          if (attempts >= 3 || (err instanceof ApiError && err.status === 503)) {
            setPaused(true); setError(isHindi ? 'आवाज़ साफ़ नहीं आ रही है। फिर कोशिश करें या लिखें।' : 'We are having trouble hearing you. Try again or type your answer.');
            return;
          }
          if (!await say(isHindi ? 'माफ़ कीजिए, आपकी बात साफ़ नहीं सुन पाया। कृपया फिर से बोलिए।' : 'I am sorry, I did not quite catch that. Could you say that again?')) return;
        }
      }
    }
    void runTurn().catch(() => {
      if (!signal.aborted) { setPhase('AI_ERROR'); setPaused(true); setError(isHindi ? 'थोड़ा रुककर फिर कोशिश करें।' : 'Please take a moment and try again.'); }
    });
    return () => { controller.abort(); stop(); };
  }, [snapshot, paused, typing, editing, retry, safetyKey, acknowledged, speak, stop, router]);

  async function resume() {
    interrupt();
    await unlock();
    if (snapshot) {
      try { setSnapshot(await getIntakeSnapshot(snapshot.interview_id)); }
      catch { setError(hi ? 'सेवा से संपर्क नहीं हो पाया।' : 'Unable to reconnect. Please try again.'); return; }
    } else { window.location.reload(); return; }
    setError(''); setEditing(false); setTyping(false); setPaused(false); setRetry(n => n + 1);
  }
  async function saveTyped() {
    if (!snapshot || !draft.trim() || submitting.current) return;
    interrupt(); submitting.current = true; setPhase('PROCESSING'); setError('');
    try {
      const next = await sendIntakeAnswer(snapshot.interview_id, draft.trim(), snapshot.revision);
      setLastTranscript(draft.trim()); setDraft(''); setSnapshot(next); setEditing(false);
      setPaused(false); setPhase(next.status === 'ACTIVE' ? 'IDLE' : 'COMPLETED');
    } catch (err) {
      const latest = await getIntakeSnapshot(snapshot.interview_id).catch(() => null);
      if (latest && latest.revision !== snapshot.revision) { setSnapshot(latest); setDraft(''); setEditing(false); }
      else { setError(err instanceof Error ? err.message : 'Please try again.'); setPhase('AI_ERROR'); }
    } finally { submitting.current = false; }
  }

  const visiblePhase = speech.speaking ? 'SPEAKING' : phase;
  const avatarState = speech.speaking ? 'speaking' : phase === 'LISTENING' || phase === 'RECORDING' ? 'listening' :
    ['TRANSCRIBING', 'PROCESSING', 'VALIDATING', 'ASKING', 'NEXT_QUESTION'].includes(phase) ? 'thinking' :
    phase.endsWith('ERROR') || phase === 'SAFETY_PAUSE' ? 'error' : 'waiting';
  const question = spokenText || snapshot?.next_question?.text || (hi ? 'आपका स्वागत है।' : 'Welcome. Make yourself comfortable.');
  const buttonClass = 'inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-teal-900/15 bg-white/80 px-5 py-3 text-base font-medium text-teal-950 transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-700';

  return <main lang={language} className="relative flex min-h-dvh flex-col overflow-x-hidden bg-[#eef5f2] text-[#193c3c]" data-testid="hands-free-interview" data-state={visiblePhase}>
    <header className="z-10 flex items-center justify-between gap-3 px-5 py-4 sm:px-10">
      <div><p className="font-semibold tracking-wide">MediKiosk</p><p className="text-sm text-teal-800">{hi ? 'आपके साथ, आपकी देखभाल के लिए' : 'Here with you, for your care'}</p></div>
      <button className={buttonClass} onClick={() => { interrupt(); setPaused(true); setHelp(true); }}><HelpCircle size={20}/>{hi ? 'मदद' : 'Help'}</button>
    </header>
    <div className="pointer-events-none absolute left-1/2 top-24 h-[50vh] w-[min(90vw,700px)] -translate-x-1/2 rounded-full bg-white/70 blur-3xl"/>
    <section className="relative mx-auto flex w-full max-w-5xl flex-1 flex-col items-center px-5">
      <div className="h-[48dvh] min-h-64 w-full sm:h-[55dvh]"><TalkingAvatar immersive mouth={speech.mouth} state={avatarState} language={language}/></div>
      <div className="relative z-10 -mt-1 w-full rounded-[2rem] bg-white/85 px-5 py-5 text-center shadow-[0_-10px_40px_10px_#eef5f2] sm:px-12">
        <p id="active-question-text" className="mx-auto max-w-3xl text-2xl font-medium leading-relaxed sm:text-3xl">{typing || editing ? snapshot?.next_question?.text || question : question}</p>
        <div role="status" aria-live="polite" className="mt-5 flex min-h-8 items-center justify-center gap-3 text-lg text-teal-700">
          {(phase === 'LISTENING' || phase === 'RECORDING') && <span className="flex h-7 items-center gap-1" aria-hidden="true">{[.5, .85, 1, .7, .4].map((scale, i) => <span key={i} className="w-1 rounded-full bg-teal-600 transition-all" style={{ height: 5 + level * 28 * scale }}/>)}</span>}
          {LABELS[visiblePhase][hi ? 1 : 0]}
        </div>
        {phase === 'SAFETY_PAUSE' && <div id="clinical-safety-alert" role="alert" className="mx-auto mt-5 max-w-2xl rounded-2xl border border-amber-300 bg-amber-50 p-5 text-left text-lg text-amber-950">
          <p>{hi ? 'अभी कर्मचारी को बुलाएँ। सहायक ने कोई कर्मचारी या आपात सेवा नहीं बुलाई है।' : 'Ask a member of staff for help now. This assistant has not contacted staff or emergency services.'}</p>
          <button className={buttonClass + ' mt-4'} onClick={() => { setAcknowledged(safetyKey); setRetry(n => n + 1); }}>{hi ? 'मदद पास है — बातचीत जारी रखें' : 'Help is here — resume conversation'}</button>
        </div>}
        {error && <p role="alert" className="mx-auto mt-4 max-w-2xl text-lg text-amber-900"><AlertCircle className="mr-2 inline" size={20}/>{error}</p>}
        {typing && safetyKey && <p id="clinical-safety-alert" role="alert" className="mt-4 rounded-2xl bg-amber-50 p-4 text-lg text-amber-950">{hi ? 'आपकी बताई तकलीफ के लिए तुरंत स्वास्थ्य कर्मचारी से मदद लें।' : 'Please ask a healthcare professional for prompt help with the symptoms you reported.'}</p>}
        {(typing || editing) && !completed && <form className="mx-auto mt-5 max-w-2xl" onSubmit={event => { event.preventDefault(); void saveTyped(); }}>
          <label htmlFor="patient-answer-input" className="sr-only">{hi ? 'आपका उत्तर' : 'Your answer'}</label>
          <textarea id="patient-answer-input" rows={3} className="w-full rounded-2xl border border-teal-200 bg-white p-4 text-xl" value={draft} onChange={e => setDraft(e.target.value)} autoFocus/>
          <button type="submit" disabled={!draft.trim() || phase === 'PROCESSING'} className={buttonClass + ' mt-3'}><Check size={20}/>{hi ? 'यह उत्तर इस्तेमाल करें' : 'Use this answer'}</button>
        </form>}
        {lastTranscript && !typing && !editing && <div className="mx-auto mt-4 max-w-2xl text-base text-slate-600">
          <p data-testid="last-transcript">“{lastTranscript}”</p>
          {phase === 'VALIDATING' && <button className="min-h-12 px-4 underline underline-offset-4" onClick={() => { interrupt(); setEditing(true); }}>{hi ? 'सुधारें' : 'Correct transcription'}</button>}
          {phase !== 'VALIDATING' && snapshot && snapshot.question_budget.answered > 0 && <button className="min-h-12 px-4 underline underline-offset-4" onClick={() => { interrupt(); router.push('/patient/review'); }}>{hi ? 'दर्ज जानकारी सुधारें' : 'Review or correct saved information'}</button>}
        </div>}
        {completed && <a id="view-completed-button" href="/patient/review" className={buttonClass + ' mt-4'}>{hi ? 'अपनी जानकारी देखें' : 'Review your information'}<ArrowRight size={20}/></a>}
      </div>
    </section>
    <footer className="relative z-10 mx-auto flex w-full max-w-4xl flex-col items-center gap-4 px-5 py-5">
      <div className="flex flex-wrap justify-center gap-3">
        {phase !== 'SAFETY_PAUSE' && <>
          <button className={buttonClass} onClick={() => { if (paused || typing || editing || phase.endsWith('ERROR')) void resume(); else { interrupt(); setPaused(true); setPhase('PAUSED'); } }}>
            {paused || typing || editing || phase.endsWith('ERROR') ? <Play size={20}/> : <Pause size={20}/>}
            {paused || typing || editing || phase.endsWith('ERROR') ? (hi ? 'शुरू करें' : 'Start') : (hi ? 'रुकें' : 'Pause')}
          </button>
          {!typing && !editing && !completed && <button id="switch-to-typing-btn" className={buttonClass} onClick={() => { interrupt(); setTyping(true); setPhase('IDLE'); }}><Keyboard size={20}/>{hi ? 'लिखकर उत्तर दें' : 'Type instead'}</button>}
          {(typing || editing) && <button className={buttonClass} onClick={() => void resume()}><Mic size={20}/>{hi ? 'बोलकर उत्तर दें' : 'Return to conversation'}</button>}
        </>}
      </div>
      <p className="text-center text-sm text-teal-800">{hi ? 'संक्षिप्त बातचीत · 5–10 प्रश्न' : 'A short conversation · 5–10 questions'}{snapshot ? ' · ' + snapshot.question_budget.answered + (hi ? ' उत्तर दिए' : ' answered') : ''}</p>
      {snapshot?.ai_warning && <p className="max-w-xl text-center text-sm text-amber-900">{hi ? 'AI सेवा उपलब्ध नहीं है। आपके उत्तर डॉक्टर के लिए सुरक्षित हो रहे हैं।' : 'The AI service is unavailable. Your answers are still being saved for your doctor.'}</p>}
      <div className="h-1 w-40 overflow-hidden rounded-full bg-teal-900/10" aria-hidden="true"><div className="h-full rounded-full bg-teal-600 transition-all duration-700" style={{ width: (completed ? 100 : (snapshot?.question_budget.answered || 0) * 10) + '%' }}/></div>
    </footer>
    {help && <div className="fixed inset-0 z-50 flex items-center justify-center bg-teal-950/40 p-6" role="dialog" aria-modal="true" aria-labelledby="help-title">
      <div className="max-w-lg rounded-3xl bg-white p-8"><h2 id="help-title" className="text-2xl font-semibold">{hi ? 'हम रुक गए हैं' : 'We have paused'}</h2><p className="my-5 text-xl">{hi ? 'कृपया पास के अस्पताल कर्मचारी को बुलाएँ। इस स्क्रीन से कर्मचारी को संदेश नहीं भेजा गया है। आप लिखकर भी उत्तर दे सकते हैं।' : 'Please ask a nearby member of hospital staff for help. No message has been sent to staff from this screen. You can also type your answers.'}</p><button className={buttonClass} onClick={() => setHelp(false)}><X size={20}/>{hi ? 'बंद करें' : 'Close'}</button></div>
    </div>}
  </main>;
}
