import React from 'react';
import { Activity } from 'lucide-react';

interface InterviewProgressProps {
  collectedCount: number;
  estimatedTotal?: number;
  completionPercentage?: number;
  language?: 'hi' | 'en';
}

export const InterviewProgress: React.FC<InterviewProgressProps> = ({
  collectedCount,
  completionPercentage = 0,
  language = 'hi',
}) => {
  const isHindi = language === 'hi';
  const progressPercent = Math.max(0, Math.min(Math.round(completionPercentage), 100));

  return (
    <div className="w-full bg-slate-50/90 border border-slate-200/80 rounded-2xl p-3.5 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-2xs">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center font-bold">
          <Activity className="w-4 h-4" />
        </div>
        <div>
          <span className="text-xs font-bold text-slate-800 block">
            {isHindi ? 'परामर्श की तैयारी' : 'Preparing Consultation Summary'}
          </span>
          <span className="text-[11px] text-slate-500 block">
            {isHindi
              ? `आवश्यक जानकारी संकलित: ${collectedCount} विषय`
              : `Information points gathered: ${collectedCount} topics`}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 w-full sm:w-auto">
        <div className="w-full sm:w-36 h-2 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-sky-500 to-teal-500 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <span className="text-xs font-bold text-slate-700 font-mono shrink-0">
          {progressPercent}%
        </span>
      </div>
    </div>
  );
};
