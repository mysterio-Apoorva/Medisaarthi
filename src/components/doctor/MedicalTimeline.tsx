import React from 'react';
import { TimelineEvent } from '@/types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { History, Calendar, Database, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';

interface MedicalTimelineProps {
  timeline: TimelineEvent[];
}

export const MedicalTimeline: React.FC<MedicalTimelineProps> = ({ timeline }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-800">
          <History className="w-4 h-4 text-sky-600" />
          <span>Longitudinal Medical Timeline</span>
        </CardTitle>
        <Badge variant="primary" size="sm">
          Chronological
        </Badge>
      </CardHeader>
      <CardContent>
        {timeline.length === 0 ? (
          <p className="text-xs text-slate-400 italic">No historical records available</p>
        ) : (
          <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
            {timeline.map((item, idx) => {
              const isLatest = idx === timeline.length - 1;
              return (
                <div key={item.id || idx} className="relative group">
                  {/* Timeline Node Icon */}
                  <div
                    className={`absolute -left-6 top-1 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-transform group-hover:scale-110 ${
                      isLatest
                        ? 'bg-sky-600 border-white ring-4 ring-sky-100 text-white'
                        : 'bg-white border-slate-300 ring-2 ring-slate-100 text-slate-500'
                    }`}
                  >
                    <div
                      className={`w-2 h-2 rounded-full ${
                        isLatest ? 'bg-white' : 'bg-slate-400'
                      }`}
                    />
                  </div>

                  {/* Timeline Event Content */}
                  <div className="bg-slate-50/70 hover:bg-slate-50 border border-slate-200/80 rounded-xl p-4 transition-colors">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                      <span className="font-bold text-xs text-sky-800 flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-sky-600" />
                        <span>{item.date}</span>
                      </span>

                      <div className="flex items-center gap-2">
                        {/* Source Tag */}
                        <span className="text-[10px] font-semibold uppercase tracking-wider bg-white border border-slate-200 text-slate-600 px-2 py-0.5 rounded-md flex items-center gap-1">
                          <Database className="w-3 h-3 text-slate-400" />
                          <span>Source: {item.source}</span>
                        </span>

                        {/* Confidence */}
                        <span className="text-[10px] font-semibold bg-emerald-50 border border-emerald-200 text-emerald-700 px-2 py-0.5 rounded-md flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3 text-emerald-600" />
                          <span>{item.confidence} Confidence</span>
                        </span>
                      </div>
                    </div>

                    <p className="text-sm font-semibold text-slate-900 mt-1">
                      {item.fact}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
