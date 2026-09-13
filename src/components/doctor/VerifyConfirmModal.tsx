'use client';

import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { CheckCircle2, ShieldCheck, AlertCircle } from 'lucide-react';

interface VerifyConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (followUp: { treatmentPlan?: string; followUpAt?: string }) => Promise<void>;
  isVerifying: boolean;
  patientName?: string;
  patientId?: string;
}

export const VerifyConfirmModal: React.FC<VerifyConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  isVerifying,
  patientName,
  patientId,
}) => {
  const [treatmentPlan, setTreatmentPlan] = useState('');
  const [followUpAt, setFollowUpAt] = useState('');
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2 text-emerald-800">
          <ShieldCheck className="w-5 h-5 text-emerald-600" />
          <span>Confirm Clinical Verification</span>
        </div>
      }
      maxWidth="md"
    >
      <div className="space-y-4">
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-950 leading-relaxed font-medium">
          <p className="font-bold text-sm text-emerald-900 mb-1">
            Doctor Verification Checklist
          </p>
          <p>
            Have you reviewed the AI-assisted summary and made any required corrections for{' '}
            <strong>{patientName || 'this patient'}</strong> (#{patientId})?
          </p>
        </div>

        <p className="text-xs text-slate-600 leading-relaxed">
          Clicking <strong>Verify Summary</strong> will mark this intake record as officially verified by{' '}
          the authenticated clinician and store the verification timestamp in the permanent clinical audit log.
        </p>

        <fieldset className="space-y-3 rounded-2xl border border-sky-100 bg-sky-50/40 p-4">
          <legend className="px-1 text-sm font-bold text-slate-900">Follow-up plan</legend>
          <p className="text-xs text-slate-600">These are clinician-entered instructions only. The follow-up assistant will never add or change treatment.</p>
          <label className="block text-xs font-semibold text-slate-700">Treatment or self-care instructions (optional)<textarea value={treatmentPlan} onChange={event => setTreatmentPlan(event.target.value)} maxLength={2000} rows={3} disabled={isVerifying} className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2 text-sm font-normal" placeholder="Record the verified plan or instructions for the patient." /></label>
          <label className="block text-xs font-semibold text-slate-700">Suggested follow-up date (optional)<input value={followUpAt} onChange={event => setFollowUpAt(event.target.value)} type="date" disabled={isVerifying} className="mt-1 block rounded-xl border border-slate-300 bg-white p-2 text-sm font-normal" /></label>
        </fieldset>

        <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2.5">
          <Button
            type="button"
            variant="outline"
            size="md"
            onClick={onClose}
            disabled={isVerifying}
            className="rounded-xl font-semibold"
            id="cancel-verify-btn"
          >
            Cancel
          </Button>

          <Button
            type="button"
            variant="success"
            size="md"
            onClick={() => onConfirm({ treatmentPlan: treatmentPlan.trim() || undefined, followUpAt: followUpAt || undefined })}
            isLoading={isVerifying}
            leftIcon={<CheckCircle2 className="w-4 h-4 text-white" />}
            className="rounded-xl font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md"
            id="confirm-verify-btn"
          >
            Verify Summary
          </Button>
        </div>
      </div>
    </Modal>
  );
};
