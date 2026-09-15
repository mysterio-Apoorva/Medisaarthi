'use client';

import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (followUp: { treatmentPlan?: string; followUpAt?: string }) => Promise<void>;
  isVerifying: boolean;
  patientName?: string;
  patientId?: string;
}

export function VerifyConfirmModal({ isOpen, onClose, onConfirm, isVerifying, patientName, patientId }: Props) {
  return <Modal isOpen={isOpen} onClose={onClose} title="Finalize clinical record" maxWidth="md">
    <div className="space-y-4">
      <p>Confirm you reviewed the history, document reconciliation, tests, vitals and saved prescription for {patientName} (#{patientId}).</p>
      <p>The saved prescription and doctor advice will be included in the finalized PDF and patient follow-up. Finalized records cannot be edited.</p>
      <p>Save all prescription changes in the treatment record before continuing.</p>
      <div className="flex justify-end gap-3">
        <Button id="cancel-verify-btn" variant="outline" onClick={onClose} disabled={isVerifying}>Cancel</Button>
        <Button id="confirm-verify-btn" onClick={() => onConfirm({})} isLoading={isVerifying}>Finalize record</Button>
      </div>
    </div>
  </Modal>;
}
