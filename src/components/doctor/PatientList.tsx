'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import { PatientListItem } from '@/types';

import { Search, CheckCircle2, ChevronRight, Clock, AlertTriangle, FileQuestion, ShieldAlert } from 'lucide-react';

interface PatientListProps {
  patients: PatientListItem[];
  isLoading?: boolean;
}

export const PatientList: React.FC<PatientListProps> = ({
  patients,
  isLoading = false,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'Ready for review' | 'Verified'>('ALL');
  const [priorityFilter, setPriorityFilter] = useState<'ALL' | 'Priority' | 'Normal'>('ALL');

  const filteredPatients = useMemo(() => {
    return patients.filter((p) => {
      const query = searchQuery.toLowerCase().trim();

      const matchesSearch =
        !query ||
        p.name.toLowerCase().includes(query) ||
        p.patient_id.toLowerCase().includes(query) ||
        (p.current_complaint && p.current_complaint.toLowerCase().includes(query)) ||
        (p.uhid && p.uhid.toLowerCase().includes(query));

      const matchesStatus =
        statusFilter === 'ALL' || p.status === statusFilter;

      const matchesPriority =
        priorityFilter === 'ALL' ||
        (priorityFilter === 'Priority'
          ? p.priority === 'Priority' || p.priority === 'Urgent'
          : p.priority === 'Normal');

      return matchesSearch && matchesStatus && matchesPriority;
    });
  }, [patients, searchQuery, statusFilter, priorityFilter]);

  return (
    <div id="patients-section" className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Search and Filters Bar */}
      <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3.5 bg-slate-50/50">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
          <input
            id="patient-search-input"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by patient name, ID (e.g. P1001), or symptom..."
            className="w-full pl-10 pr-4 py-2 bg-white rounded-xl border border-slate-200 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 font-medium"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-2.5 text-xs text-slate-400 hover:text-slate-600"
            >
              Clear
            </button>
          )}
        </div>

        {/* Filter Badges */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter */}
          <div className="flex items-center bg-white p-1 rounded-xl border border-slate-200 text-xs font-semibold">
            {(['ALL', 'Ready for review', 'Verified'] as const).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                  statusFilter === st
                    ? 'bg-sky-600 text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                {st === 'ALL' ? 'All Status' : st}
              </button>
            ))}
          </div>

          {/* Priority Quick Filter */}
          <div className="flex items-center bg-white p-1 rounded-xl border border-slate-200 text-xs font-semibold">
            {(['ALL', 'Priority', 'Normal'] as const).map((pr) => (
              <button
                key={pr}
                type="button"
                onClick={() => setPriorityFilter(pr)}
                className={`px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer ${
                  priorityFilter === pr
                    ? 'bg-slate-800 text-white shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                {pr === 'ALL' ? 'All Priority' : pr === 'Priority' ? '⚡ Priority' : 'Normal'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading ? (
        <div className="p-8 space-y-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="h-16 bg-slate-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : filteredPatients.length === 0 ? (
        /* Empty State */
        <div className="p-12 text-center" id="empty-patient-list">
          <FileQuestion className="w-12 h-12 mx-auto text-slate-300 mb-3" />
          <h3 className="text-base font-bold text-slate-800">No patients matched your filter</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            Try adjusting your search keywords or resetting the status and priority filters.
          </p>
          <button
            onClick={() => {
              setSearchQuery('');
              setStatusFilter('ALL');
              setPriorityFilter('ALL');
            }}
            className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-colors cursor-pointer"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        /* Patient Queue Table */
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" id="patient-queue-table">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <th className="py-3.5 px-5">Patient Name & ID</th>
                <th className="py-3.5 px-4">Demographics</th>
                <th className="py-3.5 px-4">Intake Complaint</th>
                <th className="py-3.5 px-4">Verification Status</th>
                <th className="py-3.5 px-4">Priority</th>
                <th className="py-3.5 px-4">Registration</th>
                <th className="py-3.5 px-5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filteredPatients.map((patient) => {
                const isPriority = patient.priority === 'Priority' || patient.priority === 'Urgent';
                const isVerified = patient.status === 'Verified';

                return (
                  <tr
                    key={patient.patient_id}
                    className="hover:bg-sky-50/40 transition-colors group"
                    id={`patient-row-${patient.patient_id}`}
                  >
                    {/* Patient & ID */}
                    <td className="py-4 px-5">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-2xl bg-slate-100 text-slate-800 font-bold flex items-center justify-center text-sm group-hover:bg-sky-100 group-hover:text-sky-700 transition-colors">
                          {patient.name.charAt(0)}
                        </div>
                        <div>
                          <Link
                            href={`/doctor/patients/${patient.patient_id}`}
                            className="font-bold text-slate-900 hover:text-sky-600 block transition-colors"
                          >
                            {patient.name}
                          </Link>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="font-mono text-xs font-semibold text-slate-500">
                              #{patient.patient_id}
                            </span>
                            {patient.uhid && (
                              <span className="text-[10px] text-slate-400">
                                • {patient.uhid}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Demographics */}
                    <td className="py-4 px-4 text-xs text-slate-600">
                      <span className="font-semibold text-slate-800">{patient.age} yrs</span> •{' '}
                      {patient.gender} • {patient.language === 'hi' ? 'Hindi' : 'English'}
                    </td>

                    {/* Current Complaint */}
                    <td className="py-4 px-4">
                      {patient.current_complaint ? (
                        <div>
                          <span className="font-semibold text-slate-900 block text-xs">
                            {patient.current_complaint}
                          </span>
                          {patient.duration && (
                            <span className="text-[11px] text-slate-500 font-medium">
                              Duration: {patient.duration} {patient.severity ? `• Sev: ${patient.severity}` : ''}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400 italic">No complaint recorded</span>
                      )}
                    </td>

                    {/* Verification Status */}
                    <td className="py-4 px-4">
                      {isVerified ? (
                        <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Verified</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-800 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full">
                          <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
                          <span>AI-assisted / unverified</span>
                        </span>
                      )}
                    </td>

                    {/* Priority Flag */}
                    <td className="py-4 px-4">
                      {isPriority ? (
                        <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-900 bg-amber-100 border border-amber-300 px-2.5 py-1 rounded-full">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                          <span>{patient.priority}</span>
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 font-medium">Routine</span>
                      )}
                    </td>

                    {/* Registration Time */}
                    <td className="py-4 px-4 text-xs font-medium text-slate-500">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span>{patient.registration_time || patient.arrival_time || 'Today'}</span>
                      </div>
                    </td>

                    {/* Action Button */}
                    <td className="py-4 px-5 text-right">
                      <Link
                        href={`/doctor/patients/${patient.patient_id}`}
                        className="inline-flex items-center gap-1 px-3.5 py-2 rounded-xl text-xs font-bold text-sky-700 bg-sky-50 hover:bg-sky-600 hover:text-white transition-all cursor-pointer shadow-2xs"
                        id={`review-patient-btn-${patient.patient_id}`}
                      >
                        <span>Review Patient</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
