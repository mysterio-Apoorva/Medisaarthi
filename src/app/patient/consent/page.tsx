'use client';

import React, { useState } from 'react';
import { STORAGE_UNAVAILABLE, useStoredPreference } from '@/lib/browser-preferences';
import { useRouter } from 'next/navigation';
import { PatientHeader } from '@/components/patient/PatientHeader';
import { ConsentCard } from '@/components/patient/ConsentCard';
import { Button } from '@/components/ui/Button';
import { ArrowRight, ArrowLeft, ShieldCheck } from 'lucide-react';
import { recordConsent } from '@/services/api';

export default function PatientConsentPage() {
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);
  const storedLanguage = useStoredPreference('medisaarthi_selected_lang');
  const language = storedLanguage === 'en' ? 'en' : 'hi';
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestError, setError] = useState<string | null>(null);
  const error = requestError || (storedLanguage === STORAGE_UNAVAILABLE ? 'Browser storage is unavailable. Enable site storage and retry.' : null);

  const handleContinue = async () => {
    if (!agreed) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const patientId = localStorage.getItem('medisaarthi_current_patient_id');
      if (!patientId) throw new Error('Sign in again to record consent.');
      const clinical = await recordConsent(patientId, 'CLINICAL_INTAKE');
      await recordConsent(patientId, 'DOCUMENT_PROCESSING');
      localStorage.setItem('medisaarthi_current_consent_id', clinical.consent_id);
      router.push('/patient/interview');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not record consent. Please retry.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoBack = () => {
    router.push('/patient/language');
  };

  const isHindi = language === 'hi';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between text-slate-900">
      <PatientHeader currentStep={3} totalSteps={4} stepName="Consent" />

      <main className="flex-1 max-w-2xl mx-auto px-4 sm:px-6 py-8 sm:py-12 flex flex-col justify-center space-y-6 w-full">
        {/* Title */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>{isHindi ? 'सहमति और गोपनीयता' : 'Privacy & Consent'}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            {isHindi ? 'इंटरव्यू शुरू करने से पहले' : 'Before we begin'}
          </h1>
          <p className="text-base text-slate-700 font-medium max-w-md mx-auto leading-relaxed">
            {isHindi
              ? 'मेदिमार्थी आपकी वर्तमान स्वास्थ्य समस्या और आपकी पिछली बीमारियों के बारे में सवाल पूछेगा। आपके उत्तर समीक्षा के लिए डॉक्टर के साथ साझा किए जाएंगे।'
              : 'Medisaarthi will ask questions about your current health problem and your medical history. Your answers will be shared with the doctor for review.'}
          </p>
        </div>

        {/* Consent Interactive Card */}
        <ConsentCard
          agreed={agreed}
          onToggleAgree={(val) => setAgreed(val)}
          language={language}
        />

        {/* Action Buttons: Agree & Continue + Go Back */}
        <div className="pt-2 max-w-md mx-auto w-full space-y-3">
          <Button
            variant="primary"
            size="xl"
            disabled={!agreed || isSubmitting}
            onClick={handleContinue}
            rightIcon={<ArrowRight className="w-5 h-5" />}
            className="w-full text-lg font-bold shadow-md rounded-2xl py-4 min-h-[56px]"
            id="agree-continue-button"
          >
            {isHindi ? 'मैं सहमत हूँ और आगे बढ़ें (I Agree & Continue)' : 'I Agree & Continue'}
          </Button>

          {error && <p className="text-center text-xs text-rose-700 font-semibold" role="alert">{error}</p>}

          <Button
            variant="outline"
            size="lg"
            onClick={handleGoBack}
            leftIcon={<ArrowLeft className="w-4 h-4" />}
            className="w-full text-sm font-semibold rounded-2xl py-3 border-slate-300 text-slate-700 hover:bg-slate-100"
            id="go-back-button"
          >
            {isHindi ? 'वापस जाएँ (Go Back)' : 'Go Back'}
          </Button>

          {!agreed && (
            <p className="text-center text-xs text-amber-700 font-medium mt-2">
              {isHindi
                ? 'कृपया आगे बढ़ने के लिए सहमति बॉक्स पर टिक करें।'
                : 'Please check the agreement box above to continue.'}
            </p>
          )}
        </div>
      </main>

      <footer className="border-t border-slate-200 py-4 text-center text-xs text-slate-500">
        Medisaarthi handles your health information in accordance with hospital privacy standards.
      </footer>
    </div>
  );
}
