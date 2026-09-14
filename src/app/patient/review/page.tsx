'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { completeInterviewSession, correctPatientFact, getIntakeSnapshot, type IntakeSnapshot } from '@/services/api';
import { PatientHeader } from '@/components/patient/PatientHeader';
import { DocumentReview } from '@/components/patient/DocumentReview';

export default function PatientReviewPage() {
  const router = useRouter();
  const [snapshot, setSnapshot] = useState<IntakeSnapshot | null>(null);
  const [edits, setEdits] = useState<Record<string,string>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dirty = snapshot ? Object.entries(snapshot.clinical_state).some(([field,value]) => edits[field] !== (Array.isArray(value) ? value.join('\n') : String(value))) : false;
  async function load(savedField?: string) {
    const id = localStorage.getItem('medisaarthi_current_interview_id');
    if (!id) { router.replace('/patient/identify'); return; }
    const data = await getIntakeSnapshot(id);
    if (['SUBMITTED','FINALIZED'].includes(data.status)) { router.replace('/patient/completed'); return; }
    setSnapshot(data);
    const values = Object.fromEntries(Object.entries(data.clinical_state).map(([field,value]) => [field, Array.isArray(value) ? value.join('\n') : String(value)]));
    setEdits(current => savedField ? {...current, [savedField]:values[savedField]} : values);
  }
  useEffect(() => { load().catch(e => setError(e.message)); }, []);
  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <PatientHeader currentStep={4} totalSteps={4} stepName="Review and consent" />
    <main className="mx-auto max-w-3xl px-4 py-8 space-y-5">
      <h1 className="text-3xl font-black">Review your information</h1>
      <p className="text-slate-600">Correct anything that is inaccurate. This is your reported history, not a diagnosis. A clinician will review it.</p>
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-rose-800">{error} <button className="underline" onClick={() => load().catch(e => setError(e.message))}>Reload</button></p>}
      {!snapshot && !error && <p role="status">Loading your saved record…</p>}
      {snapshot && <>
        {snapshot.priority_flags.map(flag => <p key={flag.code} role="alert" className="rounded-xl bg-rose-50 border border-rose-200 p-3 text-rose-900">{flag.message} Do not delay urgent care to complete this form.</p>)}
        <section className="rounded-2xl bg-white border border-slate-200 p-5 space-y-4">
          <h2 className="text-lg font-bold">Your recorded answers · {snapshot.completion.completion_percentage}% complete</h2>
          {Object.entries(snapshot.clinical_state).map(([field, original]) => <div key={field} className="flex gap-3 items-end">
            <label className="flex-1 text-sm font-semibold capitalize">{field.replaceAll('_',' ')}
              {typeof original === 'boolean' ? <select aria-label={field.replaceAll('_',' ')} className="mt-1 block w-full border border-slate-300 rounded-lg p-2" value={edits[field]} onChange={e => { setEdits({...edits,[field]:e.target.value}); setConfirmed(false); }}><option value="true">Yes</option><option value="false">No</option></select> : <textarea aria-label={field.replaceAll('_',' ')} rows={Array.isArray(original) ? 2 : 1} className="mt-1 block w-full border border-slate-300 rounded-lg p-2 font-normal normal-case" value={edits[field] ?? ''} onChange={e => { setEdits({...edits,[field]:e.target.value}); setConfirmed(false); }} />}
              {Array.isArray(original) && <span className="block text-xs font-normal normal-case text-slate-500">One item per line. Empty means none reported.</span>}
            </label>
            <button disabled={busy} className="rounded-lg bg-sky-100 text-sky-800 px-3 py-2 text-sm font-bold disabled:opacity-50" onClick={async () => {
              setBusy(true); setError('');
              try { const value = typeof original === 'boolean' ? edits[field] === 'true' : Array.isArray(original) ? edits[field].split('\n').map(s => s.trim()).filter(Boolean) : field === 'severity' ? Number(edits[field]) : edits[field];
                await correctPatientFact(snapshot.encounter_id, field, value, snapshot.revision); await load(field);
              } catch (e) { setError(e instanceof Error ? e.message : 'Correction failed'); } finally { setBusy(false); }
            }}>Save {field.replaceAll('_',' ')}</button>
          </div>)}
        </section>
        <DocumentReview encounterId={snapshot.encounter_id} allowUpload />
        {!snapshot.question_budget.complete && <button className="min-h-12 rounded-xl bg-teal-100 px-5 py-3 text-teal-950" onClick={() => router.push('/patient/interview')}>Return to the conversation</button>}
        {snapshot.completion.critical_missing.length > 0 && <div className="rounded-xl bg-amber-50 p-4">Not yet recorded: {snapshot.completion.critical_missing.join(', ')}. {snapshot.question_budget.complete ? 'Your clinician will review the missing information. You do not need another interview question.' : <button className="underline" onClick={() => router.push('/patient/interview')}>Continue interview</button>}</div>}
        <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4 bg-white"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} className="mt-1" /><span>I have reviewed this information and consent to sharing this record with my authorized clinician. Submission consent version 2026-09.</span></label>
        {dirty && <p role="status" className="text-amber-800">Save each changed field before submitting. Your other unsaved corrections stay in this form.</p>}
        <button id="submit-reviewed-intake" className="w-full rounded-2xl bg-sky-600 text-white p-4 font-bold disabled:opacity-50" disabled={!confirmed || dirty || busy || snapshot.question_budget.answered < 5 || (snapshot.completion.critical_missing.length > 0 && !snapshot.question_budget.complete)} onClick={async () => {
          setBusy(true); setError('');
          try { await completeInterviewSession(snapshot.encounter_id, snapshot.revision, confirmed); router.push('/patient/completed'); }
          catch (e) { setError(e instanceof Error ? e.message : 'Submission failed'); } finally { setBusy(false); }
        }}>{busy ? 'Saving…' : 'Submit for clinician review'}</button>
      </>}
    </main>
  </div>;
}
