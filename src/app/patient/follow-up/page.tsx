'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowRight, CheckCircle2, HeartPulse, Volume2 } from 'lucide-react';
import { PatientHeader } from '@/components/patient/PatientHeader';
import { TalkingAvatar } from '@/components/patient/TalkingAvatar';
import { useAssistantSpeech } from '@/components/patient/useAssistantSpeech';
import { VoiceRecorder } from '@/components/patient/VoiceRecorder';
import {
  answerFollowUp,
  getCurrentUser,
  getPatientFollowUps,
  startFollowUpCheckIn,
  transcribeFollowUpAudio,
  type FollowUpCheckIn,
  type FollowUpPlanOverview,
} from '@/services/api';

export default function PatientFollowUpPage() {
  const [plans, setPlans] = useState<FollowUpPlanOverview[]>([]);
  const [checkIn, setCheckIn] = useState<FollowUpCheckIn | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const speech = useAssistantSpeech();

  const load = (resume = false) => getCurrentUser().then(async user => {
    if (user.role !== 'PATIENT' || !user.patient_id) throw new Error('Sign in as a patient to use follow-up check-in.');
    const savedPlans = await getPatientFollowUps(user.patient_id);
    setPlans(savedPlans);
    const active = savedPlans.find(p => p.sessions.some(s => s.status === 'ACTIVE'));
    if (resume && active) setCheckIn(await startFollowUpCheckIn(active.plan.follow_up_plan_id));
  });
  useEffect(() => { load(true).catch(reason => setError(reason instanceof Error ? reason.message : 'Could not load follow-up.')).finally(() => setLoading(false)); }, []);

  const begin = async (planId: string) => {
    setBusy(true); setError(''); speech.stop();
    try { const result = await startFollowUpCheckIn(planId); setCheckIn(result); setDraft(''); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not start follow-up.'); }
    finally { setBusy(false); }
  };
  const submit = async () => {
    if (!checkIn?.next_question || !draft.trim()) return;
    setBusy(true); setError(''); speech.stop();
    try {
      const result = await answerFollowUp(checkIn.session.follow_up_session_id, checkIn.next_question.id, draft, checkIn.session.revision);
      setCheckIn(result); setDraft(''); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save your response.'); }
    finally { setBusy(false); }
  };
  const transcribe = async (audio: Blob, filename: string) => {
    if (!checkIn) return;
    setBusy(true); setError(''); speech.stop();
    try { const result = await transcribeFollowUpAudio(checkIn.session.follow_up_session_id, audio, filename, checkIn.session.revision); setDraft(result.transcript); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not transcribe this recording.'); }
    finally { setBusy(false); }
  };
  const question = checkIn?.next_question;
  const language = checkIn?.record_context.language || 'en';
  const avatarState = busy || speech.loading ? 'thinking' : speech.speaking ? 'speaking' : 'waiting';

  return <div className="min-h-screen bg-slate-50 text-slate-900"><PatientHeader showDoctorPortalLink={false} />
    <main className="mx-auto max-w-3xl space-y-6 px-4 py-8 sm:px-6">
      <div className="text-center"><div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-600 text-white"><HeartPulse className="h-6 w-6" /></div><h1 className="text-3xl font-black tracking-tight">Patient follow-up</h1><p className="mt-2 text-slate-600">A short check-in based on your finalized record. It does not prescribe or change treatment.</p></div>
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900">{error}</p>}
      {loading ? <p role="status" className="text-center text-slate-600">Loading your follow-up plan…</p> : !plans.length ? <section className="rounded-2xl border border-slate-200 bg-white p-6 text-center"><h2 className="font-bold">No finalized follow-up plan yet</h2><p className="mt-2 text-sm text-slate-600">Your clinician enables follow-up after finalizing the consultation.</p><Link href="/patient" className="mt-4 inline-block text-sm font-bold text-sky-700 underline">Return to patient home</Link></section> : !checkIn ? <section className="space-y-3">{plans.filter(item => item.plan.status === 'ACTIVE').map(item => <article key={item.plan.follow_up_plan_id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-bold">Follow-up check-in</h2><p className="mt-1 text-sm text-slate-600">Created {new Date(item.plan.created_at).toLocaleDateString()}{item.plan.follow_up_at ? ` · suggested follow-up ${item.plan.follow_up_at}` : ''}</p>{item.last_check_in && <p className="mt-2 text-sm text-slate-700">Last check-in: {new Date(item.last_check_in.started_at).toLocaleDateString()} · risk {item.last_check_in.risk_level}</p>}</div><button type="button" disabled={busy} onClick={() => void begin(item.plan.follow_up_plan_id)} className="min-h-11 rounded-xl bg-sky-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">Start check-in</button></div>{item.plan.instructions && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">Doctor-recorded instructions: {item.plan.instructions}</p>}{item.alerts.filter(alert => alert.status === 'OPEN').map(alert => <p key={alert.follow_up_alert_id} className="mt-3 rounded-lg bg-rose-50 p-3 text-sm font-semibold text-rose-900"><AlertTriangle className="mr-1 inline h-4 w-4" />{alert.message}</p>)}</article>)}</section> : <section className="space-y-5 rounded-3xl border border-sky-100 bg-white p-5 sm:p-7">
        <TalkingAvatar mouth={speech.mouth} state={avatarState} language={language} />
        <section className="rounded-xl bg-slate-50 p-3 space-y-2"><h2 className="font-bold">Stored treatment plan</h2>{checkIn.record_context.medications.map((medicine, index) => <p key={index}>{medicine}</p>)}<p>{checkIn.record_context.doctor_instructions}</p></section>
        {checkIn.responses.length > 0 && <section className="space-y-2"><h2 className="font-bold">Saved responses</h2>{checkIn.responses.map(response => <div key={response.follow_up_response_id}><p>{response.question_text}</p><p className="font-semibold">{response.response_text}</p></div>)}</section>}
        {checkIn.ai_warning && <p role="alert">{checkIn.ai_warning} <button className="underline" disabled={busy} onClick={() => void begin(checkIn.plan.follow_up_plan_id)}>Retry question</button></p>}
        {checkIn.alerts.filter(alert => alert.status === 'OPEN').map(alert => <p key={alert.follow_up_alert_id} role="alert" className="rounded-xl bg-rose-50 p-4 text-sm font-semibold text-rose-900"><AlertTriangle className="mr-1 inline h-4 w-4" />{alert.message}</p>)}
        {!question ? <div className="text-center"><CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" /><h2 className="mt-3 text-xl font-bold">Check-in recorded</h2><p className="mt-2 text-sm text-slate-600">Your responses were added to your timeline for clinician review.</p><button type="button" onClick={() => { setCheckIn(null); void load(); }} className="mt-4 text-sm font-bold text-sky-700 underline">View follow-up history</button></div> : <>
          <div><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold uppercase tracking-wider text-sky-700">Follow-up question</p><button type="button" onClick={() => void speech.speak(question.text, language)} className="inline-flex items-center gap-1 rounded-lg border border-sky-200 px-3 py-1.5 text-xs font-bold text-sky-800"><Volume2 className="h-3.5 w-3.5" /> Listen</button></div><h2 className="mt-3 text-xl font-bold leading-relaxed">{question.text}</h2></div>
          <textarea value={draft} onChange={event => setDraft(event.target.value)} rows={4} disabled={busy} className="w-full rounded-xl border border-slate-300 p-3 text-base" placeholder="Speak or type your response…" aria-label="Follow-up response" />
          <div className="flex flex-wrap items-center justify-between gap-3"><VoiceRecorder language={language} isProcessing={busy} onRecorded={transcribe} /><button type="button" disabled={busy || !draft.trim() || !question.text} onClick={() => void submit()} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50">Save response <ArrowRight className="h-4 w-4" /></button></div>
          {speech.notice && <p className="text-sm text-amber-800">{speech.notice}</p>}
        </>}
      </section>}
    </main>
  </div>;
}
