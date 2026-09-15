'use client';

import React from 'react';
import { DoctorSummaryResponse } from '@/types';
import { Activity, FileHeart, Pill, ShieldAlert, AlertTriangle, HelpCircle, Database } from 'lucide-react';


interface StructuredClinicalDataProps {
  summary: DoctorSummaryResponse;
}

export const StructuredClinicalData: React.FC<StructuredClinicalDataProps> = ({ summary }) => {
  const cc = summary.current_complaint;
  const pastHistory = summary.past_medical_history || [];
  const medications = summary.medications || [];
  const allergies = summary.allergies || [];  const missingInfo = summary.missing_information || [];
  const priorityFlags = summary.priority_flags || [];
  const meta = summary.interview_metadata;

  return (
    <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6" id="structured-data-section">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-slate-800 text-white flex items-center justify-center font-bold shadow-xs">
            <Database className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">
              Underlying Structured Clinical Facts
            </h2>
            <p className="text-xs text-slate-500 font-medium">
              Source-of-truth records with extraction source and confidence
            </p>
          </div>
        </div>

        <span className="text-xs font-bold text-slate-600 bg-slate-100 border border-slate-200 px-3 py-1 rounded-full">
          {meta.status === 'FINALIZED' ? 'Clinician-finalized record' : 'Awaiting clinician finalization'}
        </span>
      </div>

      {/* 2-Column Grid for Structured Entities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Col: Current Complaint Details */}
        <div className="p-5 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-700">
              <Activity className="w-4 h-4 text-sky-600" />
              <span>Current Intake Complaint</span>
            </div>
            <span className="text-[11px] font-bold text-sky-700 bg-sky-50 border border-sky-200 px-2 py-0.5 rounded">
              {meta.status?.replaceAll('_', ' ') || 'Status unavailable'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-white rounded-xl border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                Chief Complaint
              </span>
              <span className="font-bold text-sm text-slate-900 block">
                {cc.chief_complaint || 'Not specified'}
              </span>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                Duration
              </span>
              <span className="font-bold text-sm text-slate-900 block">
                {cc.duration || 'Not specified'}
              </span>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                Severity Rating
              </span>
              <span className="font-bold text-sm text-amber-900 block font-mono">
                {cc.severity ?? 'Not recorded'}
              </span>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                Location
              </span>
              <span className="font-bold text-sm text-slate-900 block">
                {cc.location || 'Not specified'}
              </span>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                Trigger / Aggravation
              </span>
              <span className="font-semibold text-xs text-slate-800 block">
                {cc.trigger || 'None specified'}
              </span>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                Associated Symptoms
              </span>
              <span className="font-semibold text-xs text-slate-800 block">
                {cc.associated_symptoms || 'None reported'}
              </span>
            </div>
          </div>

          {/* Individual Clinical Fact Extraction Lineage */}
          {cc.facts && cc.facts.length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-slate-200">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                Extraction Facts Trace ({cc.facts.length} facts recorded)
              </span>
              <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                {cc.facts.map((fact, idx) => (
                  <span
                    key={idx}
                    className={`text-[11px] px-2.5 py-1 rounded-lg border font-medium ${
                      fact.source === 'DOCTOR_ENTERED'
                        ? 'bg-emerald-50 text-emerald-900 border-emerald-300 font-semibold'
                        : 'bg-white text-slate-700 border-slate-200'
                    }`}
                  >
                    <strong>{fact.field_name}:</strong> {fact.value}{' '}
                    <span className="text-[10px] text-slate-400 font-normal">
                      ({fact.source === 'DOCTOR_ENTERED' ? 'Clinician confirmed' : fact.source.replaceAll('_', ' ')})
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Col: Past History & Medications */}
        <div className="space-y-4">
          {/* Past History */}
          <div className="p-5 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-700">
              <div className="flex items-center gap-2">
                <FileHeart className="w-4 h-4 text-sky-600" />
                <span>Past Medical History</span>
              </div>
              <span className="text-[11px] text-slate-500 font-normal">
                {pastHistory.length} Recorded
              </span>
            </div>

            {pastHistory.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No past medical history recorded.</p>
            ) : (
              <div className="space-y-2">
                {pastHistory.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-white rounded-xl border border-slate-200 flex items-center justify-between text-xs"
                  >
                    <div>
                      <span className="font-bold text-slate-900 block">{item.condition}</span>
                      {item.date && (
                        <span className="text-[11px] text-slate-500">Recorded: {item.date}</span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400">
                      Source: {item.source || 'Source unavailable'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Active Medications */}
          <div className="p-5 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-3">
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-700">
              <div className="flex items-center gap-2">
                <Pill className="w-4 h-4 text-sky-600" />
                <span>Active Medications</span>
              </div>
              <span className="text-[11px] text-slate-500 font-normal">
                {medications.length} Prescriptions
              </span>
            </div>

            {medications.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No active medications recorded.</p>
            ) : (
              <div className="space-y-2">
                {medications.map((med, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-white rounded-xl border border-slate-200 flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900">{med.name}</span>
                        <span className="font-mono text-[11px] font-semibold bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                          {med.dosage}
                        </span>
                      </div>
                      {med.frequency && (
                        <span className="text-[11px] text-slate-500 block mt-0.5">
                          Frequency: {med.frequency}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400">Source: {med.source}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Triad: Allergies, Checklist/Missing, Priority Flags */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs pt-2">
        {/* Allergies */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
            <span>Allergy Status</span>
          </div>
          <div className="p-3 bg-white rounded-xl border border-slate-200">
            <span className="font-bold text-slate-900 block">{summary.allergy_status}</span>
            {allergies.length > 0 && (
              <div className="mt-2 space-y-1">
                {allergies.map((a, idx) => (
                  <div key={idx} className="text-rose-900 font-medium">
                    • {a.allergen} {a.reaction && `(${a.reaction})`}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Missing Information */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-sky-600" />
            <span>Missing Information</span>
          </div>
          <div className="p-3 bg-white rounded-xl border border-slate-200 space-y-1">
            {missingInfo.length === 0 ? (
              <span className="text-slate-500 italic">None recorded</span>
            ) : (
              missingInfo.map((m, idx) => (
                <div key={idx} className="text-slate-700">
                  • <strong>{m.field_name}:</strong> {m.description}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Priority Flags */}
        <div className="p-4 rounded-2xl bg-slate-50/70 border border-slate-200 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>Priority Flags</span>
          </div>
          <div className="p-3 bg-white rounded-xl border border-slate-200">
            {priorityFlags.length === 0 ? (
              <span className="text-slate-500 italic">No explicit priority or safety flags recorded.</span>
            ) : (
              priorityFlags.map((flag, idx) => (
                <div key={idx} className="text-amber-950 font-bold bg-amber-50 p-2 rounded-lg border border-amber-200 mb-1">
                  ⚡ {flag}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
