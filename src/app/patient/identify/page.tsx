'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, ShieldCheck, UserCheck } from 'lucide-react';
import { PatientHeader } from '@/components/patient/PatientHeader';
import { Button } from '@/components/ui/Button';
import { login, registerPatient } from '@/services/api';

type Mode = 'signin' | 'register';

export default function PatientIdentifyPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState<'Male' | 'Female' | 'Other'>('Other');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const continueAsPatient = (patientId: string) => {
    localStorage.setItem('medisaarthi_current_patient_id', patientId);
    router.push('/patient/language');
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === 'signin') {
        const user = await login(email, password);
        if (user.role !== 'PATIENT' || !user.patient_id) throw new Error('Please use a patient account for the intake portal.');
        continueAsPatient(user.patient_id);
      } else {
        const parsedAge = Number(age);
        if (!Number.isInteger(parsedAge) || parsedAge < 0 || parsedAge > 130) throw new Error('Enter a valid age.');
        const registered = await registerPatient({ name, age: parsedAge, gender, language: 'en', email, password });
        continueAsPatient(registered.patient_id);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not verify your details. Please retry.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between text-slate-900">
      <PatientHeader currentStep={1} totalSteps={4} stepName="Secure identification" />
      <main className="flex-1 max-w-2xl mx-auto px-4 sm:px-6 py-10 w-full flex items-center">
        <section className="w-full bg-white rounded-3xl border border-slate-200 shadow-lg p-6 sm:p-9 space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex gap-2 items-center rounded-full bg-sky-100 text-sky-800 px-3 py-1 text-xs font-bold"><UserCheck className="w-4 h-4" /> Secure patient access</div>
            <h1 className="text-2xl sm:text-3xl font-black">Confirm your details</h1>
            <p className="text-sm text-slate-600">Your identity is verified before any clinical record can be opened.</p>
          </div>
          <div className="flex rounded-xl bg-slate-100 p-1 text-sm font-bold">
            {(['signin', 'register'] as Mode[]).map((item) => <button key={item} type="button" onClick={() => { setMode(item); setError(null); }} className={`flex-1 rounded-lg px-3 py-2 transition-colors ${mode === item ? 'bg-white shadow-sm text-sky-700' : 'text-slate-600'}`}>{item === 'signin' ? 'Sign in' : 'Create account'}</button>)}
          </div>
          <form onSubmit={submit} className="space-y-4">
            {mode === 'register' && <><label className="block text-xs font-bold uppercase tracking-wide">Full name<input required value={name} onChange={(event) => setName(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" /></label><div className="grid grid-cols-2 gap-3"><label className="block text-xs font-bold uppercase tracking-wide">Age<input required type="number" min="0" max="130" value={age} onChange={(event) => setAge(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" /></label><label className="block text-xs font-bold uppercase tracking-wide">Gender<select value={gender} onChange={(event) => setGender(event.target.value as typeof gender)} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm"><option>Female</option><option>Male</option><option>Other</option></select></label></div></>}
            <label className="block text-xs font-bold uppercase tracking-wide">Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" /></label>
            <label className="block text-xs font-bold uppercase tracking-wide">Password<input required type="password" minLength={10} value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" /></label>
            {error && <p role="alert" className="flex gap-2 text-sm text-rose-700"><AlertCircle className="w-4 h-4 shrink-0" />{error}</p>}
            <Button type="submit" variant="primary" size="xl" isLoading={busy} className="w-full" rightIcon={<ArrowRight className="w-5 h-5" />}>{mode === 'signin' ? 'Securely continue' : 'Create account and continue'}</Button>
          </form>

        </section>
      </main>
      <footer className="border-t border-slate-200 py-4 text-center text-xs text-slate-500 flex justify-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-600" /> Credentials are never stored in browser local storage.</footer>
    </div>
  );
}
