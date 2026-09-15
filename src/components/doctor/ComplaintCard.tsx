import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Activity, Clock, Flame } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';

interface ComplaintCardProps {
  complaint: string;
  duration: string;
  severity: string;
  associatedSymptoms: string[];
}

export const ComplaintCard: React.FC<ComplaintCardProps> = ({
  complaint,
  duration,
  severity,
  associatedSymptoms,
}) => {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-700">
          <Activity className="w-4 h-4 text-sky-600" />
          <span>Current Chief Complaint</span>
        </CardTitle>
        <Badge variant="primary" size="sm">
          Active Concern
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Main Complaint Title */}
        <div className="p-4 rounded-xl bg-sky-50/60 border border-sky-100/80">
          <div className="text-xs font-bold uppercase tracking-wider text-sky-700">
            Reported Concern
          </div>
          <div className="text-xl font-black text-slate-900 mt-0.5">
            {complaint || 'No complaint specified'}
          </div>
        </div>

        {/* Duration & Severity Matrix */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold mb-1">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>Duration</span>
            </div>
            <div className="text-base font-bold text-slate-900">
              {duration || 'Recent'}
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-amber-50/50 border border-amber-100">
            <div className="flex items-center gap-1.5 text-xs text-amber-800 font-semibold mb-1">
              <Flame className="w-3.5 h-3.5 text-amber-600" />
              <span>Reported Severity</span>
            </div>
            <div className="text-base font-bold text-amber-950 font-mono">
              {severity || '5/10'}
            </div>
          </div>
        </div>

        {/* Associated Symptoms */}
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
            Associated Symptoms
          </div>
          {associatedSymptoms && associatedSymptoms.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {associatedSymptoms.map((sym, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1 bg-slate-100 hover:bg-slate-200/70 border border-slate-200/80 text-slate-800 rounded-lg text-xs font-medium transition-colors"
                >
                  {sym}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">None reported during interview</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
