'use client';

import React, { useState, useEffect } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { DoctorSummaryResponse, DoctorSummaryEditRequest } from '@/types';
import { updateDoctorSummary } from '@/services/api';
import { Save, Edit3, AlertCircle, Plus, Trash2 } from 'lucide-react';

interface EditSummaryModalProps {
  isOpen: boolean;
  onClose: () => void;
  summary: DoctorSummaryResponse;
  onSaveSuccess: (updatedFields: string[]) => void;
}

export const EditSummaryModal: React.FC<EditSummaryModalProps> = ({
  isOpen,
  onClose,
  summary,
  onSaveSuccess,
}) => {
  const cc = summary.current_complaint;

  // Form State
  const [chiefComplaint, setChiefComplaint] = useState(cc.chief_complaint || '');
  const [duration, setDuration] = useState(cc.duration || '');
  const [severity, setSeverity] = useState(cc.severity || '');
  const [location, setLocation] = useState(cc.location || '');
  const [trigger, setTrigger] = useState(cc.trigger || '');
  const [associatedSymptoms, setAssociatedSymptoms] = useState(cc.associated_symptoms || '');

  // Lists State
  const [pastHistory, setPastHistory] = useState(
    summary.past_medical_history?.map((h) => ({ condition: h.condition, date: h.date || '' })) || []
  );
  const [medications, setMedications] = useState(
    summary.medications?.map((m) => ({ name: m.name, dosage: m.dosage || '', frequency: m.frequency || '' })) || []
  );
  const [allergies, setAllergies] = useState(
    summary.allergies?.map((a) => ({ allergen: a.allergen, reaction: a.reaction || '' })) || []
  );

  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setChiefComplaint(cc.chief_complaint || '');
      setDuration(cc.duration || '');
      setSeverity(cc.severity || '');
      setLocation(cc.location || '');
      setTrigger(cc.trigger || '');
      setAssociatedSymptoms(cc.associated_symptoms || '');
      setPastHistory(
        summary.past_medical_history?.map((h) => ({ condition: h.condition, date: h.date || '' })) || []
      );
      setMedications(
        summary.medications?.map((m) => ({ name: m.name, dosage: m.dosage || '', frequency: m.frequency || '' })) || []
      );
      setAllergies(
        summary.allergies?.map((a) => ({ allergen: a.allergen, reaction: a.reaction || '' })) || []
      );
      setErrorMessage(null);
    }
  }, [isOpen, summary]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMessage(null);

    const editPayload: DoctorSummaryEditRequest = {
      chief_complaint: chiefComplaint.trim() || undefined,
      duration: duration.trim() || undefined,
      severity: severity.trim() || undefined,
      location: location.trim() || undefined,
      trigger: trigger.trim() || undefined,
      associated_symptoms: associatedSymptoms.trim() || undefined,
      past_medical_history: pastHistory.map((h) => ({
        condition: h.condition.trim(),
        date: h.date.trim() || undefined,
        source: 'doctor_verified',
      })),
      medications: medications.map((m) => ({
        name: m.name.trim(),
        dosage: m.dosage.trim(),
        frequency: m.frequency.trim() || undefined,
        source: 'doctor_verified',
      })),
      allergies: allergies.map((a) => ({
        allergen: a.allergen.trim(),
        reaction: a.reaction.trim() || undefined,
        source: 'doctor_verified',
      })),
    };

    try {
      const res = await updateDoctorSummary(summary.patient_snapshot.patient_id, editPayload);
      setIsSaving(false);
      onSaveSuccess(res.updated_fields);
      onClose();
    } catch (err: any) {
      setIsSaving(false);
      setErrorMessage(err?.message || 'Failed to save doctor corrections. Please try again.');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <Edit3 className="w-5 h-5 text-sky-600" />
          <span>Doctor Correction & Clinical Edit</span>
        </div>
      }
      maxWidth="2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4" id="doctor-edit-form">
        <div className="p-3 bg-sky-50 border border-sky-200 rounded-xl text-xs text-sky-900 leading-relaxed font-medium">
          Your corrections create a verified fact version and a recorded audit event.
        </div>

        {errorMessage && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-900 font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Current Complaint Fields */}
        <div className="space-y-3 border-t border-slate-100 pt-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-800 block">
            Current Complaint Details
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                Chief Complaint
              </label>
              <input
                id="edit-chief-complaint"
                type="text"
                value={chiefComplaint}
                onChange={(e) => setChiefComplaint(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                Duration
              </label>
              <input
                id="edit-duration"
                type="text"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                Severity (e.g. 7, 8, 8/10)
              </label>
              <input
                id="edit-severity"
                type="text"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                Location
              </label>
              <input
                id="edit-location"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Left anterior chest"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                Trigger / Aggravating Factor
              </label>
              <input
                id="edit-trigger"
                type="text"
                value={trigger}
                onChange={(e) => setTrigger(e.target.value)}
                placeholder="e.g. Walking, Physical exertion"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                Associated Symptoms
              </label>
              <input
                id="edit-associated-symptoms"
                type="text"
                value={associatedSymptoms}
                onChange={(e) => setAssociatedSymptoms(e.target.value)}
                placeholder="e.g. Sweating, breathlessness"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-2.5">
          <Button
            type="button"
            variant="outline"
            size="md"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-xl font-semibold"
            id="cancel-edit-btn"
          >
            Cancel
          </Button>

          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isSaving}
            leftIcon={<Save className="w-4 h-4 text-white" />}
            className="rounded-xl font-bold bg-sky-600 hover:bg-sky-700 shadow-sm"
            id="save-edit-btn"
          >
            Save Corrections
          </Button>
        </div>
      </form>
    </Modal>
  );
};
