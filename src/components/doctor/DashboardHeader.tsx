import React from 'react';
import { DashboardStats } from '@/types';
import { Users, CheckCircle2, Clock, AlertTriangle, RefreshCw } from 'lucide-react';

interface DashboardHeaderProps {
  stats: DashboardStats | null;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  stats,
  onRefresh,
  isLoading = false,
}) => {
  const statCards = [
    {
      title: 'Patients Waiting',
      value: stats?.patientsWaiting ?? '—',
      desc: 'Assigned active encounters',
      icon: Users,
      color: 'sky',
      bg: 'bg-sky-50/80 border-sky-200 text-sky-700',
      iconBg: 'bg-sky-600 text-white',
    },
    {
      title: 'Interviews Completed',
      value: stats?.interviewsCompleted ?? '—',
      desc: 'Pre-consultation ready',
      icon: CheckCircle2,
      color: 'emerald',
      bg: 'bg-emerald-50/80 border-emerald-200 text-emerald-800',
      iconBg: 'bg-emerald-600 text-white',
    },
    {
      title: 'Needs Review',
      value: stats?.needsReview ?? '—',
      desc: 'Pending doctor sign-off',
      icon: Clock,
      color: 'amber',
      bg: 'bg-amber-50/80 border-amber-200 text-amber-900',
      iconBg: 'bg-amber-500 text-white',
    },
    {
      title: 'Priority Reviews',
      value: stats?.priorityReviews ?? '—',
      desc: 'Requires early attention',
      icon: AlertTriangle,
      color: 'rose',
      bg: 'bg-rose-50/80 border-rose-200 text-rose-800',
      iconBg: 'bg-rose-600 text-white',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Salutation & Refresh Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              Clinical review queue
            </h1>
          </div>
          <p className="text-sm font-medium text-slate-500 mt-1">
            Persisted pre-consultation encounters assigned to your account
          </p>
        </div>

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="self-start sm:self-auto inline-flex items-center gap-2 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 shadow-2xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh Queue</span>
          </button>
        )}
      </div>

      {/* Metrics Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className={`p-4 sm:p-5 rounded-2xl border shadow-2xs transition-all hover:shadow-xs ${card.bg}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider opacity-80">
                  {card.title}
                </span>
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center shadow-2xs ${card.iconBg}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-3">
                <div className="text-3xl font-black tracking-tight text-slate-900 font-mono">
                  {card.value}
                </div>
                <div className="text-xs text-slate-600 font-medium mt-1">
                  {card.desc}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
