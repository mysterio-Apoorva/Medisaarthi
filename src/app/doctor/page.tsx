'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { PatientListItem, DashboardStats } from '@/types';
import { getDoctorPatients, getDashboardStats } from '@/services/api';
import { DashboardHeader } from '@/components/doctor/DashboardHeader';
import { PatientList } from '@/components/doctor/PatientList';
import {
  HeartPulse,
  Menu,
  X,
  Stethoscope,
  UserCheck,
  Sparkles,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';

export default function DoctorDashboardPage() {
  const [patients, setPatients] = useState<PatientListItem[]>([]);
  const [stats, setStats] = useState<DashboardStats>({
    patientsWaiting: 0,
    interviewsCompleted: 0,
    needsReview: 0,
    priorityReviews: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const pList = await getDoctorPatients();
      setPatients(pList);

      const currentStats = await getDashboardStats();
      setStats(currentStats);
      setIsLoading(false);
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(
        err?.message || 'Unable to connect to the Medisaarthi backend server. Please verify the backend is running.'
      );
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between text-slate-900">
      {/* Top Professional Doctor Header */}
      <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-sky-500 text-slate-950 flex items-center justify-center font-bold shadow-md">
              <HeartPulse className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-base tracking-tight">MEDISAARTHI</span>
                <span className="text-[10px] font-bold uppercase bg-slate-800 text-sky-400 border border-slate-700 px-2 py-0.5 rounded">
                  Clinical Portal
                </span>
              </div>
              <p className="text-xs text-slate-400">Doctor Dashboard</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-xs text-slate-300">
              <UserCheck className="w-4 h-4 text-sky-400" />
              <span>Authenticated clinician session</span>
            </div>

            <Link
              href="/patient"
              className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 rounded-xl font-bold transition-colors shadow-xs"
            >
              Patient App
            </Link>

            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="sm:hidden p-1.5 text-slate-400 hover:text-white"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Doctor Dashboard Container */}
      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
        {/* Error Banner */}
        {errorMessage && (
          <div className="p-4 rounded-2xl bg-rose-50 border-2 border-rose-300 text-rose-900 flex items-center justify-between gap-3 shadow-sm animate-in fade-in">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
              <span className="text-sm font-semibold">{errorMessage}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              leftIcon={<RefreshCw className="w-4 h-4" />}
              className="bg-white border-rose-300 text-rose-800 hover:bg-rose-100 shrink-0 font-bold"
              id="retry-doctor-queue-btn"
            >
              Retry
            </Button>
          </div>
        )}

        {/* Header with KPI cards */}
        <DashboardHeader
          stats={stats}
          onRefresh={loadData}
          isLoading={isLoading}
        />

        {/* Patient Queue & Clinical Review Table */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <Stethoscope className="w-4 h-4 text-sky-600" />
              <span>Today's Pre-Consultation Patient Queue</span>
            </h2>
            <span className="text-xs text-slate-500 font-medium">
              Live records from the secured local clinical store
            </span>
          </div>

          <PatientList
            patients={patients}
            isLoading={isLoading}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 px-6 text-center text-xs text-slate-500">
        Medisaarthi Clinical Intelligence • AI-assisted pre-consultation information requires attending physician review and verification.
      </footer>
    </div>
  );
}
