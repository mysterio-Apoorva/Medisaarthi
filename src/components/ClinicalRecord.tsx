'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { downloadRecordPdf, getEncounterRecord, saveObservation, savePrescription, voidObservation, type EncounterRecord, type Medicine } from '@/services/api';

const vitalUnits: Record<string, string> = { 'Systolic blood pressure': 'mmHg', 'Diastolic blood pressure': 'mmHg', 'Temperature': 'C', 'Pulse': 'beats/min', 'SpO2': '%', 'Weight': 'kg', 'Height': 'cm' };

export function ClinicalRecord({ encounterId, clinician = false, readOnly = false, onChange }: { encounterId: string; clinician?: boolean; readOnly?: boolean; onChange?: () => void }) {
  const [record, setRecord] = useState<EncounterRecord | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [advice, setAdvice] = useState('');
  const [noMedicinesReason, setNoMedicinesReason] = useState('');
  const [followUpAt, setFollowUpAt] = useState('');
  const [allergiesReviewed, setAllergiesReviewed] = useState(false);
  const [voidReasons, setVoidReasons] = useState<Record<string, string>>({});
  const [draftId, setDraftId] = useState(() => crypto.randomUUID());
  const loadVersion = useRef<object>({});
  const load = useCallback((hydratePrescription = true) => {
    const version = {};
    loadVersion.current = version;
    return getEncounterRecord(encounterId).then(saved => {
    if (version !== loadVersion.current) return;
    setRecord(saved);
    setAllergiesReviewed(false);
    if (!hydratePrescription) return;
    setMedicines(saved.prescription?.medicines || []);
    setAdvice(saved.prescription?.advice || '');
    setNoMedicinesReason(saved.prescription?.no_medicines_reason || '');
    setFollowUpAt(saved.prescription?.follow_up_at || '');
    });
  }, [encounterId]);
  useEffect(() => { load().catch(e => setError(e.message)); return () => { loadVersion.current = {}; }; }, [load]);
  async function perform(action: () => Promise<unknown>, success: string, reload = true, hydratePrescription = false) {
    setBusy(true); setError(''); setNotice('');
    try { await action(); if (reload) { await load(hydratePrescription); onChange?.(); } setNotice(success); }
    catch (e) { setError(e instanceof Error ? e.message : 'The operation failed. Please retry.'); }
    finally { setBusy(false); }
  }
  const editable = record && !readOnly && record.status !== 'FINALIZED' && (clinician || ['ACTIVE', 'PATIENT_REVIEW'].includes(record.status));
  const input = 'block w-full rounded-lg border border-slate-300 p-2 text-sm bg-white';
  const button = 'rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 font-semibold text-sky-900 disabled:opacity-50';
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-5 text-left" data-testid="clinical-record">
    <h2 className="text-xl font-bold">Tests, vitals and treatment record</h2>
    {error && <p role="alert" className="text-rose-800">{error} <button className="underline" disabled={busy} onClick={() => perform(load, 'Saved record reloaded.', false)}>Reload saved record</button></p>}
    {notice && <p role="status" className="text-emerald-800">{notice}</p>}
    {!record && !error && <p>Loading saved clinical record...</p>}
    {record && <>
      <h3 className="font-bold">Recorded measurements</h3>
      {!record.observations.length && <p>No tests or vitals recorded.</p>}
      {record.observations.map(o => <div key={o.observation_id} className="rounded-lg border p-3 space-y-2">
        <p>{o.kind}: {o.name} — {o.value} {o.unit}</p><p className="text-xs">{new Date(o.measured_at).toLocaleString()} · {o.source}</p>
        {o.source === 'CALCULATED' && <p className="text-xs">Calculated from the latest saved height and weight in this encounter. Correct or withdraw those source readings to update BMI.</p>}
        {o.voided_at ? <p>Withdrawn: {o.void_reason}</p> : editable && o.source !== 'CALCULATED' && <div className="flex gap-2"><input aria-label={`Reason to withdraw ${o.name}`} className={input} value={voidReasons[o.observation_id] || ''} onChange={e => setVoidReasons({ ...voidReasons, [o.observation_id]: e.target.value })} placeholder="Reason for withdrawing an incorrect reading" /><button type="button" disabled={busy || !voidReasons[o.observation_id]?.trim()} className={button} onClick={() => perform(() => voidObservation(encounterId, o.observation_id, voidReasons[o.observation_id]), 'Reading withdrawn; its audit history is retained.')}>Withdraw</button></div>}
      </div>)}
      {editable && <form className="grid gap-3 sm:grid-cols-2" onSubmit={e => {
        e.preventDefault(); const form = e.currentTarget; const data = new FormData(form);
        void perform(async () => { await saveObservation(encounterId, { kind: data.get('kind') as 'VITAL' | 'TEST', name: String(data.get('name')), value: Number(data.get('value')), unit: String(data.get('unit')), measured_at: new Date(String(data.get('measured_at'))).toISOString(), request_id: draftId }); form.reset(); setDraftId(crypto.randomUUID()); }, 'Measurement saved to the clinical record.');
      }}>
        <label>Type<select name="kind" aria-label="Type" className={input}><option value="VITAL">Vital</option><option value="TEST">Test result</option></select></label>
        <label>Name<input name="name" required maxLength={120} list={`vital-names-${encounterId}`} className={input} onChange={e => { const form = e.currentTarget.form; const unit = form?.elements.namedItem('unit'); const kind = form?.elements.namedItem('kind'); if (unit instanceof HTMLInputElement && kind instanceof HTMLSelectElement && kind.value === 'VITAL' && vitalUnits[e.target.value]) unit.value = vitalUnits[e.target.value]; }} /></label>
        <datalist id={`vital-names-${encounterId}`}>{Object.keys(vitalUnits).map(name => <option key={name} value={name} />)}</datalist>
        <label>Measured value<input name="value" type="number" step="any" required className={input} /></label>
        <label>Unit<input name="unit" required maxLength={40} className={input} /></label>
        <label>Measurement time<input name="measured_at" type="datetime-local" required className={input} /></label>
        <button className={button} disabled={busy}>Save measurement</button>
        <p className="text-xs sm:col-span-2">Enter an actual measurement. Record systolic and diastolic blood pressure separately. Height and weight calculate BMI automatically; missing readings stay unrecorded.</p>
      </form>}
      <h3 className="font-bold">Doctor prescription and advice</h3>
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm" role={record.allergies?.length ? 'alert' : undefined}>
        <p className="font-semibold">Recorded allergy information</p>
        <p>{record.allergies === null ? 'Allergy information has not been recorded. Confirm it with the patient.' : record.allergies.length ? record.allergies.join('; ') : 'No known allergies reported.'}</p>
        {clinician && <p>Review this information against every medicine. This record does not provide a complete drug allergy or interaction check.</p>}
      </div>
      {clinician && editable && record.status === 'SUBMITTED' ? <form className="space-y-4" onSubmit={e => { e.preventDefault(); void perform(() => savePrescription(encounterId, { expected_revision: record.prescription?.revision || 0, medicines, advice, no_medicines_reason: medicines.length ? null : noMedicinesReason.trim() || null, follow_up_at: followUpAt || null, allergies_reviewed: allergiesReviewed, allergy_review: record.allergies }), 'Prescription saved. Review the complete record before finalizing.', true, true); }}>
        {medicines.map((medicine, index) => <fieldset key={index} className="grid gap-3 sm:grid-cols-2 rounded-xl border p-3"><legend>Medicine {index + 1}</legend>{(['name', 'strength', 'dose', 'frequency', 'duration', 'route', 'instructions'] as const).map(field => <label className="capitalize" key={field}>{field}<input aria-label={`Medicine ${index + 1} ${field}`} required maxLength={field === 'instructions' ? 1000 : field === 'name' ? 160 : field === 'route' ? 80 : 100} className={input} value={medicine[field] ?? ''} onChange={e => setMedicines(medicines.map((m, i) => i === index ? { ...m, [field]: e.target.value } : m))} /></label>)}<button type="button" className={button} disabled={busy} onClick={() => setMedicines(medicines.filter((_, i) => i !== index))}>Remove medicine {index + 1}</button></fieldset>)}
        <button type="button" className={button} disabled={busy || medicines.length >= 50} onClick={() => setMedicines([...medicines, { name: '', strength: '', dose: '', frequency: '', duration: '', route: '', instructions: '' }])}>Add medicine</button>
        {!!medicines.length && <label className="flex items-start gap-2 text-sm"><input type="checkbox" required checked={allergiesReviewed} onChange={e => setAllergiesReviewed(e.target.checked)} />I reviewed the recorded allergy information against every prescribed medicine.</label>}
        {!medicines.length && <label className="block">Reason no medicines are prescribed<textarea required className={input} value={noMedicinesReason} onChange={e => setNoMedicinesReason(e.target.value)} /></label>}
        <label className="block">Doctor advice / remedies<textarea required maxLength={6000} className={input} value={advice} onChange={e => setAdvice(e.target.value)} /></label>
        <label className="block">Follow-up date (optional)<input type="date" className={input} value={followUpAt} onChange={e => setFollowUpAt(e.target.value)} /></label>
        <button className={button} disabled={busy}>Save prescription</button>
      </form> : record.prescription ? <div className="space-y-2">{record.prescription.medicines.map((m, i) => <p key={i}>{m.name}{m.strength ? ` (${m.strength})` : ''} — {m.dose}, {m.frequency}, {m.duration}, {m.route}{m.instructions ? `. ${m.instructions}` : ''}</p>)}{record.prescription.no_medicines_reason && <p>{record.prescription.no_medicines_reason}</p>}<p>{record.prescription.advice}</p><p>Prescriber: {record.prescription.doctor_name}</p>{record.prescription.follow_up_at && <p>Follow-up: {record.prescription.follow_up_at}</p>}</div> : <p>A doctor has not saved a treatment plan yet.</p>}
      {record.pdf_available && <button type="button" className={button} disabled={busy} onClick={() => perform(() => downloadRecordPdf(encounterId), 'PDF generated; download started.', false)}>Download finalized medical PDF</button>}
    </>}
  </section>;
}
