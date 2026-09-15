'use client';

import React, { useState } from 'react';
import { STORAGE_UNAVAILABLE, useStoredPreference } from '@/lib/browser-preferences';
import { useRouter } from 'next/navigation';
import { Language } from '@/types';
import { PatientHeader } from '@/components/patient/PatientHeader';
import { LanguageSelector } from '@/components/patient/LanguageSelector';
import { Button } from '@/components/ui/Button';
import { ArrowRight, Languages, Leaf, Stethoscope } from 'lucide-react';
import type { CareMode } from '@/services/api';

export default function LanguageSelectionPage() {
  const router = useRouter();
  const storedLanguage = useStoredPreference('medisaarthi_selected_lang');
  const storedMode = useStoredPreference('medisaarthi_care_mode');
  const [languageChoice, setSelectedLanguage] = useState<Language | null>(null);
  const [modeChoice, setCareMode] = useState<CareMode | null>(null);
  const selectedLanguage = languageChoice ?? (storedLanguage === 'en' ? 'en' : 'hi');
  const careMode = modeChoice ?? (storedMode === 'AYUSH' ? 'AYUSH' : 'MODERN');
  const [error, setError] = useState('');

  const handleContinue = () => {
    try {
      localStorage.setItem('medisaarthi_selected_lang', selectedLanguage);
      localStorage.setItem('medisaarthi_care_mode', careMode);
    } catch { setError('Your selection could not be saved. Enable site storage and retry.'); return; }
    router.push('/patient/consent');
  };

  const isHindi = selectedLanguage === 'hi';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between text-slate-900">
      <PatientHeader currentStep={2} totalSteps={4} stepName="Language" />
      {error && <p role="alert" className="p-4 text-rose-800">{error}</p>}
      {storedLanguage === STORAGE_UNAVAILABLE && <p role="alert">Browser storage is unavailable. Enable site storage and retry.</p>}

      <main className="flex-1 max-w-2xl mx-auto px-4 sm:px-6 py-8 sm:py-12 flex flex-col justify-center space-y-8 w-full">
        {/* Title & Prompt */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-100 text-sky-800 text-xs font-bold mb-1">
            <Languages className="w-3.5 h-3.5 text-sky-600" />
            <span>भाषा चयन / Language Selection</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            अपनी भाषा चुनें / Choose your language
          </h1>
          <p className="text-base text-slate-600 max-w-md mx-auto">
            {isHindi
              ? 'जिस भाषा में आप बातचीत करना चाहते हैं, उस पर टैप करें।'
              : 'Select the language you feel most comfortable reading and speaking.'}
          </p>
        </div>

        {/* Big Language Selection Cards */}
        <LanguageSelector
          selected={selectedLanguage}
          onSelect={(lang) => setSelectedLanguage(lang)}
        />

        <section className="space-y-3" aria-labelledby="care-mode-heading">
          <div className="text-center"><h2 id="care-mode-heading" className="font-bold text-slate-900">Choose the consultation history</h2><p className="mt-1 text-sm text-slate-600">AYUSH mode adds patient-reported Ayurveda history. It does not create a diagnosis.</p></div>
          <div className="grid gap-3 sm:grid-cols-2">
            <button type="button" onClick={() => setCareMode('MODERN')} className={`min-h-24 rounded-2xl border-2 p-4 text-left transition ${careMode === 'MODERN' ? 'border-sky-600 bg-sky-50' : 'border-slate-200 bg-white hover:border-sky-300'}`} aria-pressed={careMode === 'MODERN'}><Stethoscope className="mb-2 h-5 w-5 text-sky-700" /><span className="block font-bold">Modern medicine</span><span className="text-xs text-slate-600">Structured medical history and safety questions.</span></button>
            <button type="button" onClick={() => setCareMode('AYUSH')} className={`min-h-24 rounded-2xl border-2 p-4 text-left transition ${careMode === 'AYUSH' ? 'border-emerald-600 bg-emerald-50' : 'border-slate-200 bg-white hover:border-emerald-300'}`} aria-pressed={careMode === 'AYUSH'}><Leaf className="mb-2 h-5 w-5 text-emerald-700" /><span className="block font-bold">AYUSH / Ayurveda</span><span className="text-xs text-slate-600">Also captures Dashavidha Pariksha and Ahara-Vihara history.</span></button>
          </div>
        </section>

        {/* Continue Button */}
        <div className="pt-4 max-w-md mx-auto w-full">
          <Button
            variant="primary"
            size="xl"
            onClick={handleContinue}
            rightIcon={<ArrowRight className="w-5 h-5" />}
            className="w-full text-lg font-bold shadow-md rounded-2xl py-4 min-h-[56px]"
            id="continue-button"
          >
            {selectedLanguage === 'hi' ? 'आगे बढ़ें (Continue)' : 'Continue'}
          </Button>
        </div>
      </main>

      <footer className="border-t border-slate-200 py-4 text-center text-xs text-slate-500">
        Selected Language: <strong>{selectedLanguage === 'hi' ? 'हिंदी (Hindi)' : 'English'}</strong>
      </footer>
    </div>
  );
}
