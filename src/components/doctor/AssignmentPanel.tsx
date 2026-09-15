'use client';
import { useState, useEffect } from 'react';
import { API_BASE_URL, type AdminUser } from '@/services/api';

export function AssignmentPanel({users}:{users:AdminUser[]}) {
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [providers,setProviders]=useState<unknown>(null);
  const [providerError,setProviderError]=useState('');
  const loadProviders = () => fetch(`${API_BASE_URL}/admin/providers`,{credentials:'include'}).then(async response=>{if(!response.ok)throw new Error('Provider status could not be loaded.');setProviders(await response.json());setProviderError('');}).catch(reason=>setProviderError(reason instanceof Error?reason.message:'Provider status is unavailable.'));
  useEffect(()=>{ void loadProviders(); },[]);
  return <form className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3" onSubmit={async e=>{
    e.preventDefault();setBusy(true);setMessage('');const form=new FormData(e.currentTarget);
    try{const response=await fetch(`${API_BASE_URL}/admin/assignments`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({doctor_user_id:form.get('doctor'),patient_id:form.get('patient')})});const data=await response.json();if(!response.ok)throw new Error(data.detail);setMessage('Clinician access granted and audited.');}catch(e){setMessage(e instanceof Error?e.message:'Assignment failed');}finally{setBusy(false);}
  }}><h2 className="text-lg font-bold">Authorize clinician access</h2><p className="text-sm text-slate-500">New patients are not automatically visible to every doctor.</p>
    <label className="block text-sm">Doctor<select aria-label="Assigned doctor" name="doctor" required className="ml-2 rounded-lg border p-2"><option value="">Select doctor</option>{users.filter(u=>u.role==='DOCTOR').map(u=><option key={u.user_id} value={u.user_id}>{u.display_name}</option>)}</select></label>
    <label className="block text-sm">Patient<select aria-label="Assigned patient" name="patient" required className="ml-2 rounded-lg border p-2"><option value="">Select patient</option>{users.filter(u=>u.role==='PATIENT'&&u.patient_id).map(u=><option key={u.user_id} value={u.patient_id!}>{u.display_name}</option>)}</select></label>
    <button disabled={busy} className="rounded-lg bg-sky-600 px-4 py-2 text-white">Assign doctor</button>{message&&<p role="status" className="text-sm">{message}</p>}
    <details><summary className="text-sm cursor-pointer font-semibold">AI provider configuration and observed health</summary>{providerError && <p role="alert">{providerError} <button type="button" onClick={loadProviders}>Retry</button></p>}<pre className="text-xs whitespace-pre-wrap mt-2">{providers ? JSON.stringify(providers,null,2) : 'Provider status has not loaded.'}</pre></details>
  </form>;
}
