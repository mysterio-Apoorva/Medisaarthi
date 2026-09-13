import React from 'react';
import Link from 'next/link';
import { ShieldCheck, Stethoscope } from 'lucide-react';
import { MediKioskLogo } from '@/components/brand/MediKioskLogo';

interface PatientHeaderProps {
  currentStep?: number;
  totalSteps?: number;
  stepName?: string;
  showDoctorPortalLink?: boolean;
}

export const PatientHeader: React.FC<PatientHeaderProps> = ({
  currentStep,
  totalSteps = 5,
  stepName,
  showDoctorPortalLink = true,
}) => {
  return (
    <header className="w-full bg-white border-b border-slate-200/80 sticky top-0 z-30 shadow-2xs">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <MediKioskLogo className="h-9 w-9 shrink-0 transition-transform group-hover:scale-105" />
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-slate-900 tracking-tight text-lg leading-none">
                MEDIKIOSK
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wider bg-sky-100 text-sky-800 px-1.5 py-0.5 rounded">
                Patient
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-medium leading-none mt-0.5">
              AI Pre-Consultation Assistant
            </p>
          </div>
        </Link>

        {/* Progress / Step or Doctor Portal Link */}
        <div className="flex items-center gap-3">
          {currentStep && (
            <div className="hidden sm:flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-200 text-xs text-slate-600 font-medium">
              <span>Step {currentStep} of {totalSteps}</span>
              {stepName && <span className="text-slate-400">• {stepName}</span>}
            </div>
          )}

          {showDoctorPortalLink && (
            <Link
              href="/doctor"
              className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-sky-700 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
            >
              <Stethoscope className="w-3.5 h-3.5 text-sky-600" />
              <span className="hidden xs:inline">Doctor Portal</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
