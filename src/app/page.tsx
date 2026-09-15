import React from 'react';
import Link from 'next/link';
import {
  UserCheck,
  Stethoscope,
  ShieldCheck,
  ArrowRight,
  Sparkles,
  } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { MediKioskLogo } from '@/components/brand/MediKioskLogo';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-sky-50/30">
      {/* Top Banner */}
      <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur-xs sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <MediKioskLogo className="h-10 w-10 shrink-0" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black text-slate-900 tracking-tight text-xl">
                  MEDIKIOSK
                </span>
                <Badge variant="primary" size="sm">
                  Hospital MVP
                </Badge>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                AI Pre-Consultation Intelligence Platform
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/patient"
              className="text-xs font-bold text-slate-700 hover:text-sky-600 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              Patient App
            </Link>
            <Link
              href="/doctor"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 px-4 py-2 rounded-xl shadow-xs transition-colors"
            >
              <Stethoscope className="w-3.5 h-3.5 text-sky-400" />
              <span>Doctor Dashboard</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pt-12 pb-16 text-center space-y-6">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-sky-100/80 border border-sky-200 text-sky-800 text-xs font-bold shadow-2xs animate-in fade-in">
          <Sparkles className="w-4 h-4 text-sky-600" />
          <span>Bridging Patient Registration & Doctor Consultation</span>
        </div>

        <h1 className="text-4xl sm:text-5xl md:text-6xl font-black text-slate-900 tracking-tight max-w-3xl mx-auto leading-tight">
          Empowering Doctors with <span className="text-sky-600">Pre-Consultation</span> Intelligence.
        </h1>

        <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
          Medisaarthi conducts guided multilingual interviews before the patient enters the clinic, converting conversational responses into structured clinical summaries for physician verification.
        </p>

        {/* Two Portals Direct CTAs */}
        <div className="pt-6 grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto text-left">
          {/* Patient Experience Card */}
          <div className="p-6 sm:p-7 rounded-3xl bg-white border-2 border-sky-200 hover:border-sky-500 shadow-lg hover:shadow-xl transition-all flex flex-col justify-between group">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-2xl bg-sky-100 text-sky-700 flex items-center justify-center font-bold">
                  <UserCheck className="w-6 h-6" />
                </div>
                <Badge variant="primary" size="sm">
                  Elderly & Rural Ready
                </Badge>
              </div>

              <h2 className="text-xl font-bold text-slate-900">
                Patient Experience
              </h2>
              <p className="text-xs text-slate-600 leading-relaxed">
                Step-by-step assisted interview in Hindi or English with large typography, voice input, and real-time symptom extraction.
              </p>

              <div className="pt-2 flex flex-wrap gap-1.5 text-[11px] text-slate-500">
                <span className="bg-slate-100 px-2 py-0.5 rounded">🇮🇳 हिंदी / English</span>
                <span className="bg-slate-100 px-2 py-0.5 rounded">🎙️ Voice Enabled</span>
                <span className="bg-slate-100 px-2 py-0.5 rounded">⚡ Zero Typing Needed</span>
              </div>
            </div>

            <div className="pt-6">
              <Link
                href="/patient"
                className="w-full inline-flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-bold text-sm shadow-md transition-all group-hover:gap-3 cursor-pointer"
              >
                <span>Launch Patient Experience</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>

          {/* Doctor Dashboard Card */}
          <div className="p-6 sm:p-7 rounded-3xl bg-slate-900 text-white border-2 border-slate-800 hover:border-sky-500 shadow-xl hover:shadow-2xl transition-all flex flex-col justify-between group">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-2xl bg-slate-800 text-sky-400 flex items-center justify-center font-bold">
                  <Stethoscope className="w-6 h-6" />
                </div>
                <Badge variant="info" size="sm" className="bg-sky-950 text-sky-300 border-sky-800">
                  Physician Verification
                </Badge>
              </div>

              <h2 className="text-xl font-bold text-white">
                Doctor Dashboard
              </h2>
              <p className="text-xs text-slate-300 leading-relaxed">
                Comprehensive clinical review with complaint severity, longitudinal timeline, medications, allergies, transcript inspection, and edit/approve workflows.
              </p>

              <div className="pt-2 flex flex-wrap gap-1.5 text-[11px] text-slate-400">
                <span className="bg-slate-800 px-2 py-0.5 rounded">⚡ Priority Triage</span>
                <span className="bg-slate-800 px-2 py-0.5 rounded">⏱️ Longitudinal Timeline</span>
                <span className="bg-slate-800 px-2 py-0.5 rounded">✏️ Edit & Sign-off</span>
              </div>
            </div>

            <div className="pt-6">
              <Link
                href="/doctor"
                className="w-full inline-flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm shadow-md transition-all group-hover:gap-3 cursor-pointer"
              >
                <span>Open Doctor Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Demo Walkthrough Story Section */}
      <section className="border-t border-slate-200/80 bg-white py-14">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 space-y-8">
          <div className="text-center max-w-2xl mx-auto space-y-2">
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
              End-to-End MVP Demonstration Story
            </h2>
            <p className="text-xs sm:text-sm text-slate-500">
              A consented intake is persisted, safety-checked, and handed to a clinician for review.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-sky-600 text-white font-black text-xs flex items-center justify-center">
                1
              </div>
              <h3 className="font-bold text-slate-900 text-sm">
                Patient Intake & AI Interview
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Sign in or register, grant consent, report chest pain naturally, and watch the persisted clinical state update.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-sky-600 text-white font-black text-xs flex items-center justify-center">
                2
              </div>
              <h3 className="font-bold text-slate-900 text-sm">
                Doctor Triage & Chart Review
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Doctor opens the assigned queue, prioritizes chest pain with breathlessness, and reviews facts with source and confidence.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-600 text-white font-black text-xs flex items-center justify-center">
                3
              </div>
              <h3 className="font-bold text-slate-900 text-sm">
                Physician Edit & Sign-off
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Doctor corrects a fact, resolves any document candidate, and finalizes the encounter with an audit trail.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Safety & Medical Disclaimers */}
      <footer className="border-t border-slate-200 bg-slate-50 py-8">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-sky-600" />
            <span>Medisaarthi Pre-Consultation Platform • Hospital Demo Version</span>
          </div>
          <p className="text-center sm:text-right">
            AI prepares clinical summaries; final clinical verification remains with the attending physician.
          </p>
        </div>
      </footer>
    </main>
  );
}
