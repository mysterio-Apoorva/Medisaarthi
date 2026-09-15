'use client';

import React from 'react';
import Link from 'next/link';
import { DoctorSummaryResponse } from '@/types';

import { Button } from '@/components/ui/Button';
import { ArrowLeft, Edit3, CheckCircle2, ShieldCheck, ShieldAlert, FileText } from 'lucide-react';

interface PatientProfileHeaderProps {
  summary: DoctorSummaryResponse;
  onOpenEdit: () => void;
  onOpenVerify: () => void;
  onOpenTranscript?: () => void;
  isVerifying?: boolean;
}

export const PatientProfileHeader: React.FC<PatientProfileHeaderProps> = ({
  summary,
  onOpenEdit,
  onOpenVerify,
  onOpenTranscript,
  isVerifying = false,
}) => {
  const isVerified = ['Verified', 'FINALIZED'].includes(summary.verification_status || '');
  const snapshot = summary.patient_snapshot;

  return (
    <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-7 space-y-5">
      {/* Breadcrumb & Verification Badge */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <Link
          href="/doctor"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-sky-600 transition-colors"
          id="back-to-queue-link"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Patient Queue</span>
        </Link>

        {/* Prominent Verification Status Indicator */}
        <div className="flex items-center gap-2" id="verification-status-container">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Intake Verification:
          </span>
          {isVerified ? (
            <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-900 border border-emerald-300 shadow-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-700" />
              <span>Verified</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300 shadow-xs">
              <ShieldAlert className="w-4 h-4 text-amber-700" />
              <span>AI-assisted / unverified</span>
            </span>
          )}
        </div>
      </div>

      {/* Main Patient Identity & Action Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        {/* Demographics */}
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-sky-600 to-teal-600 text-white flex items-center justify-center font-black text-2xl shadow-md shrink-0 ring-4 ring-sky-50">
            {snapshot.name ? snapshot.name.charAt(0) : 'P'}
          </div>

          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900" id="patient-name-header">
                {snapshot.name}
              </h1>
              <span className="font-mono text-xs font-bold bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg border border-slate-200" id="patient-id-badge">
                #{snapshot.patient_id}
              </span>
              {snapshot.uhid && (
                <span className="text-xs font-medium text-slate-500">
                  UHID: {snapshot.uhid}
                </span>
              )}
            </div>

            <p className="text-sm font-medium text-slate-600 flex flex-wrap items-center gap-2 pt-0.5">
              {snapshot.age && <span className="font-bold text-slate-900">{snapshot.age} yrs</span>}
              {snapshot.gender && <span>• {snapshot.gender}</span>}
              {snapshot.phone && <span>• 📞 {snapshot.phone}</span>}
              {snapshot.preferred_language && (
                <span>• Preferred: {snapshot.preferred_language === 'hi' ? 'Hindi (हिंदी)' : 'English'}</span>
              )}
            </p>

            {isVerified && (
              <p className="text-xs text-emerald-800 font-semibold flex items-center gap-1.5 pt-1">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Clinician verified</span>
              </p>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-3">
          {onOpenTranscript && (
            <Button
              variant="outline"
              size="md"
              onClick={onOpenTranscript}
              leftIcon={<FileText className="w-4 h-4 text-slate-600" />}
              className="rounded-xl font-bold"
              id="view-transcript-btn"
            >
              Interview Transcript
            </Button>
          )}

          <Button
            variant="secondary"
            size="md"
            onClick={onOpenEdit}
            disabled={isVerified || summary.interview_metadata.status !== 'SUBMITTED'}
            leftIcon={<Edit3 className="w-4 h-4 text-slate-700" />}
            className="rounded-xl font-bold bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-800"
            id="edit-summary-btn"
          >
            Edit Summary
          </Button>

          <Button
            variant={isVerified ? 'outline' : 'success'}
            size="md"
            onClick={onOpenVerify}
            disabled={isVerified || summary.interview_metadata.status !== 'SUBMITTED'}
            isLoading={isVerifying}
            leftIcon={<CheckCircle2 className="w-4 h-4 text-white" />}
            className={`rounded-xl font-bold shadow-sm ${
              isVerified
                ? 'border-emerald-600 text-emerald-800 bg-emerald-50 hover:bg-emerald-100'
                : 'bg-emerald-600 hover:bg-emerald-700 text-white'
            }`}
            id="verify-summary-btn"
          >
            {isVerified ? 'Finalized' : 'Verify Summary'}
          </Button>
        </div>
      </div>
    </div>
  );
};
