'use client';

import React, { useState, useEffect, useCallback, use } from 'react';
import Link from 'next/link';
import { DoctorSummaryResponse, DoctorNarrativeResponse, DoctorEditAuditItem, BackendInterviewDetailResponse } from '@/types';
import { getDoctorSummary, getDoctorNarrative, getDoctorAudit, verifyDoctorSummary, getInterviewDetail } from '@/services/api';
import { PatientProfileHeader } from '@/components/doctor/PatientProfileHeader';
import { NarrativeSummaryCard } from '@/components/doctor/NarrativeSummaryCard';
import { StructuredClinicalData } from '@/components/doctor/StructuredClinicalData';
import { EncounterReviewPanel } from '@/components/doctor/EncounterReviewPanel';
import { DoctorAuditTrail } from '@/components/doctor/DoctorAuditTrail';
import { EditSummaryModal } from '@/components/doctor/EditSummaryModal';
import { VerifyConfirmModal } from '@/components/doctor/VerifyConfirmModal';
import { InterviewDrawer } from '@/components/doctor/InterviewDrawer';
import { CheckCircle2, AlertCircle, FileQuestion, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export default function DoctorPatientProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {  const resolvedParams = use(params);
  const patientId = resolvedParams.id;

  // Data State
  const [summary, setSummary] = useState<DoctorSummaryResponse | null>(null);
  const [narrative, setNarrative] = useState<DoctorNarrativeResponse | null>(null);
  const [auditEntries, setAuditEntries] = useState<DoctorEditAuditItem[]>([]);
  const [interviewDetail, setInterviewDetail] = useState<BackendInterviewDetailResponse | null>(null);

  // UI State
  const [isLoading, setIsLoading] = useState(true);
  const [isNarrativeLoading, setIsNarrativeLoading] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'info' | 'warning' } | null>(null);

  // Load all patient data from live backend
  const loadAllData = useCallback(() => getDoctorSummary(patientId).then(async sumData => {
      setErrorMessage(null);
      if (!sumData) {
        setIsLoading(false);
        return;
      }
      setSummary(sumData);

      // 2. Fetch narrative summary
      setIsNarrativeLoading(true);
      try {
        const narrData = await getDoctorNarrative(patientId);
        setNarrative(narrData);
      } catch {
        setErrorMessage('The narrative could not be loaded. Reload the record to retry.');
      } finally {
        setIsNarrativeLoading(false);
      }

      // 3. Fetch audit history
      try {
        const auditList = await getDoctorAudit(patientId);
        setAuditEntries(auditList);
      } catch { setErrorMessage('The audit history could not be loaded. Reload to retry.'); }

      // 4. Fetch interview transcript if interview_id exists
      if (sumData.interview_metadata?.interview_id) {
        try {
          const detail = await getInterviewDetail(sumData.interview_metadata.interview_id);
          setInterviewDetail(detail);
        } catch { setErrorMessage('The interview transcript could not be loaded. Reload to retry.'); }
      }

      setIsLoading(false);
    }).catch(err => {
      setIsLoading(false);
      setErrorMessage(
        err instanceof Error ? err.message : 'Unable to load clinical records from backend server. Please check backend connectivity.'
      );
    }), [patientId]);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  // Show Toast
  const triggerToast = (text: string, type: 'success' | 'info' | 'warning' = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4500);
  };

  // Handle Edit Success
  const handleEditSuccess = async (updatedFields: string[]) => {
    triggerToast(
      `Saved corrections for: ${updatedFields.join(', ')}. Verification is required again.`,
      'warning'
    );
    // Refresh all data
    await loadAllData();
  };

  // Handle Verification Confirm
  const handleVerifyConfirm = async (followUp: { treatmentPlan?: string; followUpAt?: string }) => {
    if (!summary) return;
    setIsVerifying(true);

    try {
      const res = await verifyDoctorSummary(summary.patient_snapshot.patient_id, followUp);
      setIsVerifying(false);
      setIsVerifyModalOpen(false);

      triggerToast(`Intake summary officially verified by ${res.verified_by}.`, 'success');
      // Refresh all data
      await loadAllData();
    } catch (err) {
      setIsVerifying(false);
      triggerToast(err instanceof Error ? err.message : 'Verification failed. Please try again.', 'warning');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen p-8 flex flex-col items-center justify-center space-y-4 bg-slate-50 text-slate-900">
        <div className="w-12 h-12 border-4 border-sky-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-base font-bold text-slate-800">Loading patient chart #{patientId}...</p>
      </div>
    );
  }

  if (errorMessage || !summary) {
    return (
      <div className="min-h-screen p-8 flex flex-col items-center justify-center space-y-4 bg-slate-50 text-slate-900 text-center">
        <FileQuestion className="w-16 h-16 text-slate-300 mx-auto" />
        <h2 className="text-2xl font-bold text-slate-900">Patient Chart Unavailable</h2>
        <p className="text-sm text-slate-500 max-w-md">
          {errorMessage || `No clinical records found for patient ID: ${patientId}`}
        </p>
        <div className="flex items-center gap-3 pt-2">
          <Button
            variant="outline"
            size="md"
            onClick={loadAllData}
            leftIcon={<RefreshCw className="w-4 h-4" />}
            className="rounded-xl font-bold"
          >
            Retry
          </Button>
          <Link
            href="/doctor"
            className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-sm font-bold shadow-sm"
          >
            Return to Patient Queue
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between text-slate-900">
      {/* Toast Notification */}
      {toastMessage && (
        <div
          className={`fixed top-6 right-6 z-50 px-5 py-3.5 rounded-2xl shadow-xl flex items-center gap-3 animate-in slide-in-from-top duration-300 text-white ${
            toastMessage.type === 'success'
              ? 'bg-emerald-600'
              : toastMessage.type === 'warning'
              ? 'bg-amber-600'
              : 'bg-sky-600'
          }`}
          id="doctor-toast-message"
        >
          {toastMessage.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-white" />
          ) : (
            <AlertCircle className="w-5 h-5 text-white" />
          )}
          <div className="font-bold text-xs sm:text-sm">{toastMessage.text}</div>
        </div>
      )}

      {/* Main Patient Chart Layout */}
      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
        {/* 1. Patient Profile Header */}
        <PatientProfileHeader
          summary={summary}
          onOpenEdit={() => setIsEditModalOpen(true)}
          onOpenVerify={() => setIsVerifyModalOpen(true)}
          onOpenTranscript={() => setIsTranscriptOpen(true)}
          isVerifying={isVerifying}
        />

        {/* 2. AI Narrative Summary Section */}
        <NarrativeSummaryCard
          narrative={narrative}
          isLoading={isNarrativeLoading}
        />

        {/* 3. Underlying Structured Clinical Facts Section */}
        <StructuredClinicalData summary={summary} />
        <EncounterReviewPanel patientId={patientId} recordRevision={summary.record_revision} onChange={loadAllData} />

        {/* 4. Doctor Edit History & Audit Trail */}
        <DoctorAuditTrail auditEntries={auditEntries} />
      </main>

      {/* Edit Summary Modal */}
      {isEditModalOpen && <EditSummaryModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        summary={summary}
        onSaveSuccess={handleEditSuccess}
      />}

      {/* Verification Confirmation Modal */}
      <VerifyConfirmModal
        isOpen={isVerifyModalOpen}
        onClose={() => setIsVerifyModalOpen(false)}
        onConfirm={handleVerifyConfirm}
        isVerifying={isVerifying}
        patientName={summary.patient_snapshot.name}
        patientId={summary.patient_snapshot.patient_id}
      />

      {/* Full Interview Transcript Drawer */}
      <InterviewDrawer
        isOpen={isTranscriptOpen}
        onClose={() => setIsTranscriptOpen(false)}
        patient={{
          patient_id: summary.patient_snapshot.patient_id,
          name: summary.patient_snapshot.name,
          language: summary.patient_snapshot.preferred_language,
        }}
        transcript={
          interviewDetail?.messages?.map((m) => ({
            id: String(m.id),
            sender: m.role === 'assistant' ? 'ai' : 'patient',
            text: m.text,
            timestamp: new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          })) || []
        }
      />

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 px-6 text-center text-xs text-slate-500">
        Medisaarthi Physician Dashboard • Clinical review and verification are required before diagnosis.
      </footer>
    </div>
  );
}
