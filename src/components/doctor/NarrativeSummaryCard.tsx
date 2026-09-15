'use client';

import React from 'react';
import { DoctorNarrativeResponse } from '@/types';
import { Sparkles, ShieldAlert } from 'lucide-react';

interface NarrativeSummaryCardProps {
  narrative: DoctorNarrativeResponse | null;
  isLoading?: boolean;
}

export const NarrativeSummaryCard: React.FC<NarrativeSummaryCardProps> = ({
  narrative,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-4">
        <div className="h-6 w-48 bg-slate-100 rounded-lg animate-pulse" />
        <div className="h-24 bg-slate-100 rounded-2xl animate-pulse" />
        <div className="h-20 bg-slate-100 rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (!narrative) {
    return (
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 text-center text-slate-400 text-sm">
        No narrative summary available.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-3xl border-2 border-sky-200 shadow-sm p-6 sm:p-8 space-y-6" id="narrative-summary-card">
      {/* Narrative Section Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-sky-600 text-white flex items-center justify-center font-bold shadow-xs">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">
              Structured Intake Narrative
            </h2>
            <p className="text-xs text-slate-500 font-medium">
              Deterministic rendering of recorded facts for clinician review
            </p>
          </div>
        </div>

        <span className="text-[11px] font-bold text-sky-800 bg-sky-50 border border-sky-200 px-3 py-1 rounded-full">
          Recorded facts
        </span>
      </div>

      {/* Verification Disclaimer */}
      <div className="p-3.5 rounded-2xl bg-amber-50/80 border border-amber-200 text-xs text-amber-900 flex items-start gap-2.5 font-medium">
        <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <span>
          <strong>Review status:</strong> {narrative.verification_note?.replaceAll('_', ' ')}. This intake is not a diagnosis.
        </span>
      </div>

      {/* Main Narrative Breakdown Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs sm:text-sm">
        {/* Patient Snapshot & Presenting Complaint */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Presenting Complaint
          </div>
          <div className="text-base font-bold text-slate-900">
            {narrative.presenting_complaint}
          </div>
          <div className="text-xs text-slate-600 font-medium pt-1">
            <strong>Snapshot:</strong> {narrative.patient_snapshot}
          </div>
        </div>

        {/* Interview Summary */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Intake Findings & Character
          </div>
          <div className="text-slate-800 whitespace-pre-line leading-relaxed font-normal">
            {narrative.interview_summary}
          </div>
        </div>

        {/* Relevant History */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Past Medical History
          </div>
          <div className="text-slate-800 whitespace-pre-line leading-relaxed font-normal">
            {narrative.relevant_history}
          </div>
        </div>

        {/* Medications & Indication */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Active Medications
          </div>
          <div className="text-slate-800 whitespace-pre-line leading-relaxed font-normal">
            {narrative.medications}
          </div>
        </div>

        {/* Allergies */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Allergies
          </div>
          <div className="text-slate-800 whitespace-pre-line leading-relaxed font-normal">
            {narrative.allergies}
          </div>
        </div>

        {/* Important Findings */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Important Clinical Findings
          </div>
          <div className="text-slate-800 whitespace-pre-line leading-relaxed font-normal">
            {narrative.important_findings}
          </div>
        </div>

        {/* Missing Information */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Missing Information
          </div>
          <div className="text-slate-800 whitespace-pre-line leading-relaxed font-normal">
            {narrative.missing_information || 'None recorded'}
          </div>
        </div>

        {/* Priority Flags */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Priority Flags
          </div>
          <div className="text-slate-800 font-semibold">
            {narrative.priority_flags && narrative.priority_flags !== 'None' ? (
              <span className="text-amber-900 bg-amber-100 border border-amber-300 px-2.5 py-1 rounded-lg">
                ⚡ {narrative.priority_flags}
              </span>
            ) : (
              <span className="text-slate-500 font-normal">No explicit priority or safety flags recorded.</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
