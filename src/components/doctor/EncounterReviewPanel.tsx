'use client';
import { useCallback, useEffect, useState } from 'react';
import { API_BASE_URL } from '@/services/api';
import { DocumentReview } from '@/components/patient/DocumentReview';
import { KnowledgePanel } from '@/components/doctor/KnowledgePanel';
import { ClinicalRecord } from '@/components/ClinicalRecord';

type ReviewData = {
  encounter: { encounter_id: string; status: string; care_mode?: string } | null;
  clinical_state: Record<string, unknown>;
  facts: { fact_id: string; field_name: string; value: unknown; source: string; evidence: string; created_at: string; status: string }[];
  reconciliation: { reconciliation_id: string; field_name: string; incoming_value: unknown; incoming_value_json?: string; incoming_source: string; status: string; document_id?: string | null; page_number?: number | null; evidence?: string | null }[];
  timeline: { event_id: string; title: string; detail?: string; occurred_at: string; source: string; verification_status?: string; document_id?: string | null; page_number?: number | null }[];
  follow_up?: { plan: { follow_up_plan_id: string; instructions?: string | null; follow_up_at?: string | null }; last_session?: { started_at: string; risk_level: string } | null; last_response?: { response_text: string; created_at: string } | null; open_alerts: { follow_up_alert_id: string; severity: string; message: string }[] } | null;
  unified_summary?: {
    sections: { title: string; items: Record<string, unknown>[] }[];
    current_red_flags: { severity?: string; message?: string; rule_id?: string }[];
    missing_information: string[];
    contradictions_requiring_review: string[];
  };
};

export function EncounterReviewPanel({ patientId, onChange, recordRevision }: { patientId: string; onChange: () => void; recordRevision?: number }) {
  const [data, setData] = useState<ReviewData | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [replacements, setReplacements] = useState<Record<string,string>>({});
  const [aiSummary, setAiSummary] = useState<{ method: string; provider: string; sections: { title: string; facts: { fact_id: string; field_name: string; value: unknown; source: string }[] }[] } | null>(null);
  const [summaryRevision, setSummaryRevision] = useState<number | undefined>();
  const load = useCallback(() => fetch(`${API_BASE_URL}/doctor/patients/${encodeURIComponent(patientId)}/summary`, { credentials:'include' }).then(async response => {
    if (!response.ok) throw new Error('Unable to load the encounter review.');
    setData(await response.json());
  }), [patientId]);
  useEffect(() => { load().catch(e => setError(e.message)); }, [load, recordRevision]);
  async function decide(id: string, action: 'APPROVED' | 'REJECTED' | 'MERGED') {
    setBusy(true); setError('');
    try {
      const replacement = action === 'MERGED' ? JSON.parse(replacements[id] || '') : undefined;
      const response = await fetch(`${API_BASE_URL}/doctor/reconciliation/${id}`, { method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action, replacement_value:replacement}) });
      if (!response.ok) { const result = await response.json(); throw new Error(result.detail || 'Reconciliation failed'); }
      await load(); onChange();
    } catch (e) { setError(e instanceof Error ? e.message : 'Review failed'); } finally { setBusy(false); }
  }
  return <section className="space-y-5">
    <KnowledgePanel />
    {error && <p role="alert" className="rounded-xl bg-rose-50 text-rose-800 p-4">{error} <button className="underline" onClick={() => load().catch(e => setError(e.message))}>Reload</button></p>}
    {data?.encounter && <>
      <ClinicalRecord key={`${data.encounter.encounter_id}-${data.encounter.status}`} encounterId={data.encounter.encounter_id} clinician onChange={() => { load().catch(e => setError(e.message)); onChange(); }} />
      <a className="inline-block text-sm text-sky-700 underline" href={`${API_BASE_URL}/doctor/encounters/${data.encounter.encounter_id}/fhir`}>Download local FHIR R4 bundle</a>
      <div className="rounded-2xl border border-sky-200 bg-white p-5 space-y-3">
        <h2 className="text-lg font-bold">AI-organized clinical summary</h2>
        <p className="text-sm text-slate-600">The local model organizes recorded facts. It cannot add diagnoses or invent missing values. The structured record remains available if the model is offline.</p>
        <button className="rounded-xl bg-sky-600 text-white px-4 py-2 text-sm font-bold disabled:opacity-50" disabled={busy} onClick={async () => {
          setBusy(true); setError('');
          try {
            const response = await fetch(`${API_BASE_URL}/doctor/encounters/${data.encounter!.encounter_id}/ai-summary`, { method:'POST',credentials:'include' });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Summary generation failed');
            setAiSummary(result);
            setSummaryRevision(recordRevision);
          } catch (e) { setError(e instanceof Error ? e.message : 'Summary unavailable'); } finally { setBusy(false); }
        }}>{busy ? 'Processing…' : 'Generate grounded AI summary'}</button>
        {aiSummary && summaryRevision === recordRevision && <div className="space-y-3" data-testid="grounded-ai-summary"><p className="text-xs text-slate-500">{aiSummary.method} · {aiSummary.provider}</p>{aiSummary.sections.map((section,index) => <div key={index}><h3 className="font-semibold">{section.title}</h3>{section.facts.map(fact => <p className="text-sm" key={fact.fact_id}>{fact.field_name.replaceAll('_',' ')}: {JSON.stringify(fact.value)} <span className="text-xs text-slate-500">({fact.source})</span></p>)}</div>)}</div>}
      </div>
      <DocumentReview encounterId={data.encounter.encounter_id} recordRevision={recordRevision} onChange={() => { load().catch(e => setError(e.message)); onChange(); }} />
      {data.unified_summary && <section className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-5 space-y-4" data-testid="unified-clinical-record">
        <div>
          <h2 className="text-lg font-bold">Unified physician handoff</h2>
          <p className="text-sm text-slate-700">This record combines patient-reported facts, uploaded-document extraction, the longitudinal timeline, and review status. It only displays stored evidence.</p>
        </div>
        {data.unified_summary.current_red_flags.length > 0 && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900"><p className="font-bold">Current red flags</p>{data.unified_summary.current_red_flags.map((flag, index) => <p key={`${flag.rule_id || index}`}>{flag.severity || 'REVIEW'}: {flag.message || flag.rule_id}</p>)}</div>}
        {data.unified_summary.contradictions_requiring_review.length > 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><span className="font-bold">Needs reconciliation:</span> {data.unified_summary.contradictions_requiring_review.map(field => field.replaceAll('_', ' ')).join(', ')}</p>}
        {data.unified_summary.sections.map(section => <div key={section.title} className="rounded-xl bg-white p-4"><h3 className="font-semibold">{section.title}</h3><ul className="mt-2 space-y-1 text-sm text-slate-700">{section.items.map((item, index) => <li key={index}>{Object.entries(item).filter(([key]) => key !== 'field').map(([key, value]) => <span key={key} className="mr-3"><span className="text-slate-500">{key.replaceAll('_', ' ')}:</span> {typeof value === 'string' ? value : JSON.stringify(value)}</span>)}</li>)}</ul></div>)}
        {data.unified_summary.missing_information.length > 0 && <p className="text-sm text-slate-600"><span className="font-semibold">Missing information:</span> {data.unified_summary.missing_information.map(field => field.replaceAll('_', ' ')).join(', ')}</p>}
      </section>}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4">
        <h2 className="text-lg font-bold">Source reconciliation</h2>
        <p className="text-sm text-slate-600">Approve replaces the current field with the incoming value. Merge lets you enter the complete reviewed value. Reject preserves the existing record.</p>
        {!data.reconciliation.some(item => item.status === 'OPEN') && <p className="text-sm text-emerald-700">No unresolved source conflicts.</p>}
        {data.reconciliation.filter(item => item.status === 'OPEN').map(item => <div key={item.reconciliation_id} className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 space-y-2" data-testid="reconciliation-item">
          <h3 className="font-semibold capitalize">{item.field_name.replaceAll('_',' ')}</h3>
          <p className="text-sm">Current: {JSON.stringify(data.clinical_state[item.field_name] ?? 'Not recorded')}</p>
          <p className="text-sm">Incoming ({item.incoming_source}): {JSON.stringify(item.incoming_value ?? JSON.parse(item.incoming_value_json || 'null'))}</p>
          {item.document_id && <p className="text-xs text-slate-600">Source document: {item.document_id}{item.page_number ? ` · page ${item.page_number}` : ''}{item.evidence ? ` · “${item.evidence}”` : ''}</p>}
          <label className="block text-xs">Reviewed merged value (JSON string, list, number, or boolean)<input className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2" value={replacements[item.reconciliation_id] || ''} onChange={e => setReplacements({...replacements,[item.reconciliation_id]:e.target.value})} placeholder='["Medication and confirmed dose"]' /></label>
          <div className="flex gap-3 text-sm font-semibold">
            {(['APPROVED','REJECTED','MERGED'] as const).map(action => <button key={action} disabled={busy || data.encounter?.status === 'FINALIZED'} onClick={() => decide(item.reconciliation_id, action)} className="rounded-lg bg-white border border-slate-300 px-3 py-2 disabled:opacity-50">{action === 'APPROVED' ? 'Approve incoming' : action === 'REJECTED' ? 'Reject incoming' : 'Save merged value'}</button>)}
          </div>
        </div>)}
      </div>
      {data.follow_up && <section className="rounded-2xl border border-teal-200 bg-teal-50/40 p-5 space-y-3"><h2 className="text-lg font-bold">Patient follow-up</h2><p className="text-sm text-slate-700">{data.follow_up.last_session ? `Last check-in: ${new Date(data.follow_up.last_session.started_at).toLocaleString()} · risk ${data.follow_up.last_session.risk_level}` : 'No patient check-in recorded yet.'}</p>{data.follow_up.last_response && <p className="rounded-xl bg-white p-3 text-sm"><span className="font-semibold">Latest patient message:</span> “{data.follow_up.last_response.response_text}”</p>}{data.follow_up.plan.instructions && <p className="text-sm text-slate-700"><span className="font-semibold">Doctor-recorded instructions:</span> {data.follow_up.plan.instructions}</p>}{data.follow_up.open_alerts.map(alert => <div key={alert.follow_up_alert_id} className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm"><p className="font-bold text-rose-900">{alert.severity}: {alert.message}</p><button disabled={busy} className="mt-2 font-semibold text-rose-800 underline disabled:opacity-50" onClick={async () => { setBusy(true); try { const response = await fetch(`${API_BASE_URL}/follow-ups/alerts/${alert.follow_up_alert_id}/acknowledge`, { method:'POST', credentials:'include' }); if (!response.ok) throw new Error('Could not acknowledge follow-up alert.'); await load(); onChange(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not acknowledge alert.'); } finally { setBusy(false); } }}>Acknowledge alert</button></div>)}</section>}
      <details className="rounded-2xl border border-slate-200 bg-white p-5"><summary className="font-bold cursor-pointer">Clinical fact provenance</summary>
        <div className="mt-4 space-y-3">{data.facts.map(fact => <div key={fact.fact_id} className="border-t border-slate-100 pt-3 text-sm"><p className="font-semibold">{fact.field_name.replaceAll('_',' ')}: {JSON.stringify(fact.value)}</p><p className="text-slate-500">{fact.source} · {fact.status} · {new Date(fact.created_at).toLocaleString()}</p><p className="mt-1">Evidence: {fact.evidence || 'No excerpt recorded'}</p></div>)}</div>
      </details>
      <details className="rounded-2xl border border-slate-200 bg-white p-5"><summary className="font-bold cursor-pointer">Patient timeline · current and historical events</summary>
        <ol className="mt-4 space-y-3">{data.timeline.map(event => <li key={event.event_id} className="border-l-2 border-sky-200 pl-3 text-sm"><p className="font-semibold">{event.title}</p><p className="text-slate-500">{new Date(event.occurred_at).toLocaleString()} · {event.source}</p></li>)}</ol>
      </details>
    </>}
  </section>;
}
