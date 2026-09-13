'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, HeartPulse, Lock, Mail, ShieldCheck, Stethoscope } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { login } from '@/services/api';

export default function DoctorLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('doctor.demo@medikiosk.local');
  const [password, setPassword] = useState('DemoPass!2026');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null);
    try { const user = await login(email, password); if (user.role !== 'DOCTOR' && user.role !== 'ADMIN') throw new Error('This account does not have clinician access.'); router.push(user.role === 'ADMIN' ? '/admin' : '/doctor'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Sign-in failed.'); }
    finally { setBusy(false); }
  };
  return <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col justify-between">
    <header className="p-6"><Link href="/" className="inline-flex gap-3 items-center"><span className="w-10 h-10 bg-sky-500 text-slate-950 rounded-2xl grid place-items-center"><HeartPulse className="w-6 h-6" /></span><span><strong className="block">MEDIKIOSK</strong><small className="text-sky-400 uppercase tracking-widest">Physician portal</small></span></Link></header>
    <main className="max-w-md w-full mx-auto px-4 py-8"><section className="rounded-3xl border border-slate-700 bg-slate-800/80 shadow-2xl p-7 sm:p-9 space-y-6"><div className="text-center"><span className="inline-flex gap-2 items-center text-xs font-bold rounded-full border border-slate-700 px-3 py-1 text-sky-300"><Stethoscope className="w-4 h-4" /> Authorized clinical access</span><h1 className="mt-3 text-3xl font-black">Physician sign-in</h1><p className="mt-2 text-sm text-slate-400">Clinician review, correction, reconciliation, and finalization are audited.</p></div><form onSubmit={submit} className="space-y-4"><label className="block text-xs font-bold uppercase tracking-wide text-slate-300">Hospital email<div className="relative mt-1.5"><Mail className="w-4 h-4 absolute left-3 top-3 text-slate-400" /><input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-xl bg-slate-950 border border-slate-700 pl-9 pr-3 py-2.5" /></div></label><label className="block text-xs font-bold uppercase tracking-wide text-slate-300">Password<div className="relative mt-1.5"><Lock className="w-4 h-4 absolute left-3 top-3 text-slate-400" /><input required type="password" minLength={10} value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-xl bg-slate-950 border border-slate-700 pl-9 pr-3 py-2.5" /></div></label>{error && <p role="alert" className="text-sm text-rose-300">{error}</p>}<Button type="submit" variant="primary" size="lg" isLoading={busy} className="w-full" rightIcon={<ArrowRight className="w-4 h-4" />}>Sign in securely</Button></form><p className="text-xs text-sky-200 bg-sky-950/30 border border-sky-500/30 rounded-xl p-3"><strong>Synthetic demo only:</strong> the prefilled account is seeded in the local database and creates a real server-side session.</p></section></main>
    <footer className="p-5 text-center text-xs text-slate-500 flex justify-center gap-2"><ShieldCheck className="w-4 h-4" /> Clinical data requires attending-clinician verification.</footer>
  </div>;
}
