import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { HelpCircle, FileSearch, ShieldAlert } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';

interface ImportantInfoProps {
  priorityFlags: string[];
  missingInfo: string[];
}

export const ImportantInfo: React.FC<ImportantInfoProps> = ({
  priorityFlags,
  missingInfo,
}) => {
  return (
    <Card className="h-full border-slate-200">
      <CardHeader>
        <CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-800">
          <FileSearch className="w-4 h-4 text-sky-600" />
          <span>Clinical Review Notes & Missing Info</span>
        </CardTitle>
        <Badge variant="warning" size="sm">
          Physician Checklist
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Priority Focus Areas */}
        {priorityFlags && priorityFlags.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
              <span>Priority Clinical Focus</span>
            </div>
            <div className="space-y-1.5">
              {priorityFlags.map((flag, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-amber-50/70 border border-amber-200 text-xs font-medium text-amber-950 flex items-start gap-2"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-600 mt-1.5 shrink-0" />
                  <span>{flag}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Missing Information Items to Inquire */}
        {missingInfo && missingInfo.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <HelpCircle className="w-3.5 h-3.5 text-sky-600" />
              <span>Recommended Information to Inquire</span>
            </div>
            <div className="space-y-1.5">
              {missingInfo.map((info, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs font-medium text-slate-800 flex items-start gap-2"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-600 mt-1.5 shrink-0" />
                  <span>{info}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
