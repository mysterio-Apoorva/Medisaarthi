'use client';

import React, { useState } from 'react';
import { DoctorEditAuditItem } from '@/types';
import { History, ChevronDown, ChevronUp, UserCheck, Clock } from 'lucide-react';

interface DoctorAuditTrailProps {
  auditEntries: DoctorEditAuditItem[];
}

export const DoctorAuditTrail: React.FC<DoctorAuditTrailProps> = ({ auditEntries }) => {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden" id="audit-trail-section">
      {/* Toggle Header */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-5 sm:p-6 bg-slate-50/70 hover:bg-slate-100/70 transition-colors text-left cursor-pointer"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-slate-800 text-white flex items-center justify-center font-bold shadow-xs">
            <History className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span>Doctor Edit History & Audit Trail</span>
              <span className="text-xs font-bold bg-slate-200 text-slate-800 px-2 py-0.5 rounded-full font-mono">
                {auditEntries.length}
              </span>
            </h2>
            <p className="text-xs text-slate-500 font-medium">
              Recorded history of clinician corrections to intake facts
            </p>
          </div>
        </div>

        <div className="text-slate-500">
          {isOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </div>
      </button>

      {/* Content */}
      {isOpen && (
        <div className="p-5 sm:p-6 border-t border-slate-100 space-y-3">
          {auditEntries.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500 italic bg-slate-50 rounded-2xl border border-slate-100">
              No clinician corrections recorded for this encounter.
            </div>
          ) : (
            <div className="space-y-3">
              {auditEntries.map((audit) => {
                const formattedTime = new Date(audit.changed_at).toLocaleString('en-IN', {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                });

                return (
                  <div
                    key={audit.audit_id}
                    className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs uppercase tracking-wider text-slate-800 bg-white border border-slate-300 px-2.5 py-0.5 rounded-md font-mono">
                          {audit.field_name}
                        </span>
                        <span className="text-slate-400 font-mono text-[11px]">
                          Audit ID: {audit.audit_id}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 pt-0.5">
                        <div className="p-2 rounded-lg bg-white border border-slate-200">
                          <span className="text-[10px] font-bold uppercase text-slate-400 block">
                            AI Original Value:
                          </span>
                          <span className="font-medium text-slate-700">
                            {audit.original_value !== null && audit.original_value !== undefined
                              ? audit.original_value
                              : '<empty>'}
                          </span>
                        </div>

                        <span className="text-slate-400 font-bold">→</span>

                        <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-950">
                          <span className="text-[10px] font-bold uppercase text-emerald-700 block">
                            Doctor Correction:
                          </span>
                          <span className="font-bold text-emerald-900">
                            {audit.corrected_value !== null && audit.corrected_value !== undefined
                              ? audit.corrected_value
                              : '<removed>'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="text-right shrink-0 space-y-1 md:border-l md:border-slate-200 md:pl-4">
                      <div className="flex items-center gap-1.5 justify-start md:justify-end text-slate-800 font-bold">
                        <UserCheck className="w-3.5 h-3.5 text-sky-600" />
                        <span>Changed by: {audit.changed_by}</span>
                      </div>
                      <div className="flex items-center gap-1 justify-start md:justify-end text-slate-500 text-[11px]">
                        <Clock className="w-3 h-3" />
                        <span>{formattedTime}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
