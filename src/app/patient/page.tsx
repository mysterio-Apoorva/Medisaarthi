'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { HeartPulse, ArrowRight, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { PatientHeader } from '@/components/patient/PatientHeader';

export default function PatientWelcomePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50/70 via-white to-slate-100 flex flex-col justify-between text-slate-900">
      <PatientHeader showDoctorPortalLink={true} />

      <main className="flex-1 max-w-2xl mx-auto px-4 sm:px-6 py-10 sm:py-16 flex flex-col items-center justify-center text-center space-y-8 w-full">
        {/* Medisaarthi Logo Icon */}
        <div className="relative">
          <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-3xl bg-gradient-to-tr from-sky-600 to-teal-500 text-white flex items-center justify-center shadow-xl shadow-sky-600/25 ring-8 ring-sky-100">
            <HeartPulse className="w-12 h-12 sm:w-14 sm:h-14" />
          </div>
        </div>

        {/* Hero Title & Subtitle */}
        <div className="space-y-4">
          <div className="text-sm font-black tracking-widest uppercase text-sky-700">
            MEDISAARTHI • मेदिमार्थी
          </div>
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
            Welcome to Medisaarthi
          </h1>
          <p className="text-xl sm:text-2xl text-slate-700 font-medium max-w-xl mx-auto leading-relaxed">
            Before you meet the doctor, Medisaarthi will ask you a few questions about your health.
          </p>
          <p className="text-base sm:text-lg text-slate-500 font-normal max-w-lg mx-auto">
            डॉक्टर से मिलने से पहले, मेदिमार्थी आपके स्वास्थ्य के बारे में कुछ आसान सवाल पूछेगा।
          </p>
        </div>

        {/* 3 Key Benefits for Rural/Elderly Patients */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left pt-2">
          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm">
            <div className="text-2xl mb-1.5">🗣️</div>
            <div className="font-bold text-sm text-slate-900">सरल और आसान</div>
            <div className="text-xs text-slate-600">Simple one-at-a-time questions</div>
          </div>
          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm">
            <div className="text-2xl mb-1.5">⏱️</div>
            <div className="font-bold text-sm text-slate-900">2 मिनट में पूरा</div>
            <div className="text-xs text-slate-600">Answer at your own pace</div>
          </div>
          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm">
            <div className="text-2xl mb-1.5">🩺</div>
            <div className="font-bold text-sm text-slate-900">डॉक्टर की तैयारी</div>
            <div className="text-xs text-slate-600">Helps your doctor help you</div>
          </div>
        </div>

        {/* Big Start Button */}
        <div className="w-full max-w-md pt-4 space-y-4">
          <Button
            variant="primary"
            size="xl"
            onClick={() => router.push('/patient/identify')}
            rightIcon={<ArrowRight className="w-6 h-6" />}
            className="w-full text-xl shadow-lg hover:shadow-xl font-bold rounded-2xl py-5 min-h-[64px]"
            id="start-button"
          >
            Start / शुरू करें
          </Button>

          {/* Privacy Note */}
          <div className="flex items-center justify-center gap-2 text-xs text-slate-600 pt-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>
              Your answers are securely shared with your doctor for review.
            </span>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-4 bg-white/70 text-center text-xs text-slate-500">
        Medisaarthi • AI-Assisted Clinical Pre-Consultation Platform
      </footer>
    </div>
  );
}
