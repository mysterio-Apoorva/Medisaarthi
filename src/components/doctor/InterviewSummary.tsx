import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Sparkles, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';

interface InterviewSummaryProps {
  summaryText: string;
  collectedPoints?: string[];
  verified?: boolean;
}

export const InterviewSummary: React.FC<InterviewSummaryProps> = ({
  summaryText,
  collectedPoints = ['Onset & Duration', 'Pain Severity (1-10)', 'Associated Symptoms', 'Prior History & Meds'],
  verified = false,
}) => {
  return (
    <Card className="h-full border-sky-200/60 bg-gradient-to-b from-white to-sky-50/20">
      <CardHeader>
        <CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-800">
          <Sparkles className="w-4 h-4 text-sky-600" />
          <span>AI Pre-Consultation Summary</span>
        </CardTitle>
        <Badge variant={verified ? 'success' : 'primary'} size="sm">
          {verified ? 'Physician Verified' : 'AI-Prepared'}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Physician Verification Disclaimer */}
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-amber-50/80 border border-amber-200/70 text-xs text-amber-900 font-medium">
          <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
          <span>
            <strong className="font-semibold">AI-generated summary</strong> • Requires physician clinical verification before diagnostic decisions.
          </span>
        </div>

        {/* Doctor-Readable Narrative */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 text-sm leading-relaxed text-slate-800 font-normal">
          {summaryText || 'No interview summary recorded.'}
        </div>

        {/* Structured Topics Extracted */}
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
            Structured Topics Covered
          </div>
          <div className="grid grid-cols-2 gap-2">
            {collectedPoints.map((point, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 p-2 rounded-lg bg-slate-50 border border-slate-100 text-xs text-slate-700 font-medium"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                <span>{point}</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
