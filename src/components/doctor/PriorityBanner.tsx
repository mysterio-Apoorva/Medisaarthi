import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface PriorityBannerProps {
  flags: string[];
  priority?: 'Normal' | 'Priority' | 'Urgent';
}

export const PriorityBanner: React.FC<PriorityBannerProps> = ({
  flags,
  priority = 'Normal',
}) => {
  if (!flags || flags.length === 0) return null;

  const isUrgent = priority === 'Urgent';

  return (
    <div
      className={`rounded-2xl p-4 sm:p-5 border flex items-start gap-4 transition-all ${
        isUrgent
          ? 'bg-rose-50/90 border-rose-200 text-rose-950'
          : 'bg-amber-50/90 border-amber-200 text-amber-950'
      }`}
    >
      <div
        className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-2xs ${
          isUrgent ? 'bg-rose-600 text-white' : 'bg-amber-500 text-white'
        }`}
      >
        <AlertTriangle className="w-5 h-5" />
      </div>

      <div className="space-y-1.5 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
            {isUrgent ? 'Urgent Clinical Review' : 'Priority Attention Flag'}
          </span>
          <span className="text-[11px] text-slate-500 font-medium">
            (Pre-consultation rule trigger • Requires physician evaluation)
          </span>
        </div>

        <div className="space-y-1">
          {flags.map((flag, idx) => (
            <p key={idx} className="text-sm font-semibold text-slate-900 flex items-start gap-2">
              <span className="text-amber-600 font-bold">•</span>
              <span>{flag}</span>
            </p>
          ))}
        </div>
      </div>
    </div>
  );
};
