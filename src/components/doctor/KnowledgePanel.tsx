'use client';
import { useState } from 'react';
import { API_BASE_URL } from '@/services/api';

export function KnowledgePanel({ admin = false }: { admin?: boolean }) {
  const [query,setQuery]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [results,setResults]=useState<{ chunk_id:string;title:string;url:string;excerpt:string;score:number }[]>([]);
  const [searched,setSearched]=useState(false);
  const [notice,setNotice]=useState('');
  return <section className="rounded-2xl bg-white border border-slate-200 p-5 space-y-3">
    <h2 className="text-lg font-bold">Approved reference search</h2>
    <p className="text-xs text-slate-500">Local vector retrieval from administrator-approved references. No patient records are indexed. Excerpts are references, not diagnoses.</p>
    <form className="flex gap-2" onSubmit={async e => {
      e.preventDefault();setBusy(true);setError('');
      try { const response=await fetch(`${API_BASE_URL}/knowledge/answer`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({query})});const data=await response.json();if(!response.ok)throw new Error(data.detail);setResults(data.results);setSearched(true);setNotice(data.method + (data.notice ? ' · '+data.notice : '')); }
      catch(e){setError(e instanceof Error?e.message:'Search unavailable');}finally{setBusy(false);}
    }}><label className="flex-1 text-sm">Reference topic<input required minLength={3} maxLength={500} value={query} onChange={e=>setQuery(e.target.value)} className="block w-full rounded-lg border border-slate-300 p-2 mt-1" /></label><button disabled={busy} className="self-end rounded-lg bg-sky-600 text-white p-2 disabled:opacity-50">Search references</button></form>
    {searched&&!results.length&&<p className="text-sm text-slate-500">No matching approved references. An administrator can add an appropriate source.</p>}
    {results.map(result=><article className="border-t border-slate-100 pt-3" key={result.chunk_id}><a href={result.url} target="_blank" rel="noreferrer" className="font-semibold text-sky-700 underline">{result.title}</a><p className="mt-1 whitespace-pre-wrap text-sm">{result.excerpt}</p><p className="text-xs text-slate-500">Similarity: {result.score.toFixed(3)} · {result.chunk_id}</p></article>)}
    {admin&&<details><summary className="cursor-pointer text-sm font-semibold">Approve and index a reference</summary><form className="mt-3 space-y-3" onSubmit={async e=>{
      e.preventDefault();const form=e.currentTarget;const fields=new FormData(form);setBusy(true);setError('');setNotice('');
      try{const response=await fetch(`${API_BASE_URL}/knowledge/references`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:fields.get('title'),source_url:fields.get('url'),text:fields.get('text'),approved:fields.has('approved')})});const data=await response.json();if(!response.ok)throw new Error(data.detail);setNotice(`Indexed ${data.chunks} chunks with ${data.embedding_model}.`);form.reset();}catch(e){setError(e instanceof Error?e.message:'Indexing failed');}finally{setBusy(false);}
    }}><label className="block text-sm">Reference title<input name="title" required minLength={3} className="block w-full rounded-lg border p-2" /></label><label className="block text-sm">Original source URL<input name="url" type="url" required className="block w-full rounded-lg border p-2" /></label><label className="block text-sm">Reference text (no patient information)<textarea name="text" required minLength={50} maxLength={8000} rows={5} className="block w-full rounded-lg border p-2" /></label><label className="flex gap-2 text-sm"><input name="approved" type="checkbox" required />I approve this source and have permission to index it.</label><button disabled={busy} className="rounded-lg bg-sky-600 text-white p-2">Index approved reference</button></form></details>}
    {busy&&<p role="status" className="text-sm">Processing locally…</p>}{notice&&<p role="status" className="text-sm text-emerald-700">{notice}</p>}{error&&<p role="alert" className="text-sm text-rose-700">{error}</p>}
  </section>;
}
