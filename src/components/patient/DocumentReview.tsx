'use client';

import { useEffect, useRef, useState } from 'react';
import { FileText, LoaderCircle, Plus, RefreshCw, ScanText, Trash2, TriangleAlert } from 'lucide-react';
import {
  API_BASE_URL,
  deleteEncounterDocument,
  type DocumentExtraction,
  type EncounterDocument,
  getDocumentExtraction,
  listEncounterDocuments,
  retryDocumentProcessing,
  uploadEncounterDocument,
} from '@/services/api';

type JobState = 'Uploading' | 'Extracting text' | 'Identifying document' | 'Extracting clinical information' | 'Matching patient history' | 'Building timeline' | 'Completed' | 'Needs review' | 'Failed';

export function DocumentReview({ encounterId, allowUpload = false }: { encounterId: string; allowUpload?: boolean }) {
  const [documents, setDocuments] = useState<EncounterDocument[]>([]);
  const [jobs, setJobs] = useState<Record<string, JobState>>({});
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<DocumentExtraction | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = async () => setDocuments(await listEncounterDocuments(encounterId));
  useEffect(() => { load().catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load documents.')); }, [encounterId]);

  const setJob = (key: string, value: JobState) => setJobs(current => ({ ...current, [key]: value }));
  const uploadMany = async (files: FileList | null) => {
    if (!files?.length) return;
    setError('');
    for (const file of Array.from(files)) {
      const key = `${file.name}-${file.size}-${file.lastModified}`;
      try {
        setJob(key, 'Uploading');
        await new Promise(resolve => window.setTimeout(resolve, 0));
        setJob(key, 'Extracting text');
        const result = await uploadEncounterDocument(encounterId, file);
        setJob(key, result.processing_status === 'PROCESSED' ? 'Completed' : 'Needs review');
      } catch (reason) {
        setJob(key, 'Failed');
        setError(reason instanceof Error ? reason.message : `Could not process ${file.name}.`);
      }
    }
    if (fileInput.current) fileInput.current.value = '';
    await load();
  };

  const inspect = async (documentId: string) => {
    try {
      setError('');
      setSelected(await getDocumentExtraction(documentId));
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load the document extraction.'); }
  };
  const retry = async (documentId: string) => {
    try {
      setError(''); setJob(documentId, 'Extracting text');
      const result = await retryDocumentProcessing(documentId);
      setJob(documentId, result.processing_status === 'PROCESSED' ? 'Completed' : 'Needs review');
      await load(); await inspect(documentId);
    } catch (reason) { setJob(documentId, 'Failed'); setError(reason instanceof Error ? reason.message : 'Could not reprocess the document.'); }
  };
  const remove = async (documentId: string) => {
    try {
      setError(''); await deleteEncounterDocument(documentId);
      if (selected?.document_id === documentId) setSelected(null);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not remove the document.'); }
  };

  return <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" aria-labelledby="documents-heading">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 id="documents-heading" className="text-lg font-bold text-slate-900">Your medical documents</h2>
        <p className="mt-1 text-sm text-slate-600">Add reports from different visits. Their original files and page evidence are preserved; extracted facts need clinician verification.</p>
      </div>
      {allowUpload && <>
        <input ref={fileInput} className="sr-only" id="document-upload" type="file" multiple accept="application/pdf,image/png,image/jpeg,image/webp" onChange={event => void uploadMany(event.target.files)} />
        <label htmlFor="document-upload" className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-sky-700"><Plus className="h-4 w-4" /> Add document</label>
      </>}
    </div>
    {Object.entries(jobs).filter(([, value]) => !['Completed', 'Needs review'].includes(value)).map(([key, value]) => <p key={key} role="status" className="flex items-center gap-2 rounded-xl bg-sky-50 p-3 text-sm text-sky-950"><LoaderCircle className="h-4 w-4 animate-spin" />{key.split('-')[0]}: {value}…</p>)}
    {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {!documents.length && <div className="rounded-xl border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500"><FileText className="mx-auto mb-2 h-6 w-6 text-slate-400" />No documents added yet. You can continue without them.</div>}
    <div className="space-y-2">
      {documents.map(document => <article key={document.document_id} className="rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0"><p className="font-semibold text-slate-900 break-words">{document.original_name}</p><p className="mt-1 text-xs text-slate-500">{document.classification || 'Unclassified'}{document.document_date ? ` · ${document.document_date}` : ''}{typeof document.entity_count === 'number' ? ` · ${document.entity_count} clinical item(s)` : ''}</p></div>
          <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${document.processing_status === 'PROCESSED' ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'}`}>{document.processing_status === 'PROCESSED' ? 'Extracted — needs review' : 'Needs review'}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-sm font-semibold">
          <button type="button" className="text-sky-700 underline" onClick={() => void inspect(document.document_id)}>Review extracted text</button>
          <a className="text-sky-700 underline" href={`${API_BASE_URL}/documents/${document.document_id}/file`}>Open original</a>
          <button type="button" className="inline-flex items-center gap-1 text-sky-700 underline" onClick={() => void retry(document.document_id)}><RefreshCw className="h-3.5 w-3.5" /> Retry</button>
          {allowUpload && <button type="button" className="inline-flex items-center gap-1 text-rose-700 underline" onClick={() => void remove(document.document_id)}><Trash2 className="h-3.5 w-3.5" /> Remove</button>}
        </div>
      </article>)}
    </div>
    {selected && <div className="rounded-2xl border border-sky-200 bg-sky-50/40 p-4 space-y-4" aria-live="polite">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-bold text-slate-900">Document review</h3><p className="text-sm text-slate-600">{selected.classification || 'Unknown'} · confidence {Math.round((selected.classification_confidence || 0) * 100)}%{selected.document_date ? ` · date ${selected.document_date}` : ''}</p></div><button type="button" className="text-sm font-semibold text-sky-700 underline" onClick={() => setSelected(null)}>Close</button></div>
      <p className="text-xs text-slate-600">Processing: {selected.processing_steps.join(' → ') || 'Needs manual review'}</p>
      {selected.review && <p className="rounded-xl bg-white p-3 text-sm text-slate-700">{selected.review.summary}{selected.review.abnormal_results.length ? ` Printed abnormal result(s): ${selected.review.abnormal_results.join('; ')}.` : ''}</p>}
      {!!selected.match_results?.length && <div className="rounded-xl bg-white p-3 text-sm"><p className="font-semibold text-slate-900">Match with your recorded history</p><div className="mt-2 flex flex-wrap gap-2">{selected.match_results.map(result => <span key={result.field_name} className={`rounded-lg px-2 py-1 text-xs font-semibold ${result.status === 'CONSISTENT' ? 'bg-emerald-50 text-emerald-800' : result.status === 'CONFLICT_REQUIRES_REVIEW' ? 'bg-amber-50 text-amber-900' : 'bg-slate-100 text-slate-700'}`}>{result.field_name.replaceAll('_',' ')}: {result.status.replaceAll('_',' ')}</span>)}</div></div>}
      {!selected.entities.length && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><TriangleAlert className="mr-1 inline h-4 w-4" />No supported clinical statements were extracted. Review the original file with the clinician.</p>}
      <div className="grid gap-3 sm:grid-cols-2">{selected.entities.map(entity => <div key={entity.entity_id} className={`rounded-xl border bg-white p-3 text-sm ${entity.abnormal_status === 'HIGH' || entity.abnormal_status === 'LOW' ? 'border-amber-300' : 'border-slate-200'}`}><p className="font-semibold text-slate-900">{entity.entity_type.replaceAll('_', ' ')}{entity.abnormal_status && entity.abnormal_status !== 'NORMAL' ? <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">{entity.abnormal_status}</span> : null}</p><p className="mt-1 break-words">{entity.value}</p><p className="mt-2 text-xs text-slate-500">Page {entity.page_number} · {Math.round(entity.confidence * 100)}% extraction confidence · {entity.verification_status.replaceAll('_', ' ')}</p><p className="mt-2 rounded bg-slate-50 p-2 text-xs text-slate-600">“{entity.evidence}”</p></div>)}</div>
      <details className="rounded-xl bg-white p-3"><summary className="cursor-pointer text-sm font-semibold"><ScanText className="mr-1 inline h-4 w-4" />Page text and OCR evidence</summary><div className="mt-3 space-y-3">{selected.pages.map(page => <details key={page.page_number} className="rounded-lg border border-slate-200 p-3"><summary className="cursor-pointer text-sm">Page {page.page_number} · {page.extraction_method} · {Math.round(page.confidence * 100)}%</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-700">{page.raw_text || 'No readable text was extracted from this page.'}</pre></details>)}</div></details>
    </div>}
  </section>;
}
