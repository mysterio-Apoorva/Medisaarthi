import React from 'react';
import { MedicalCondition } from '@/types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { FileHeart } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';

interface PastMedicalHistoryProps {
  conditions: MedicalCondition[];
}

export const PastMedicalHistory: React.FC<PastMedicalHistoryProps> = ({ conditions }) => {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-800">
          <FileHeart className="w-4 h-4 text-sky-600" />
          <span>Past Medical History</span>
        </CardTitle>
        <Badge variant="primary" size="sm">
          {conditions.length} Recorded
        </Badge>
      </CardHeader>
      <CardContent>
        {conditions.length === 0 ? (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 text-xs text-slate-500 italic text-center">
            No pre-existing chronic conditions recorded.
          </div>
        ) : (
          <div className="space-y-3">
            {conditions.map((item, idx) => (
              <div
                key={item.id || idx}
                className="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200/80 flex items-start justify-between gap-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-slate-900">
                      {item.condition}
                    </span>
                    <span className="text-[10px] font-bold bg-sky-100 text-sky-800 px-2 py-0.5 rounded">
                      Since {item.year}
                    </span>
                  </div>
                  {item.notes && (
                    <p className="text-xs text-slate-600 mt-1">
                      {item.notes}
                    </p>
                  )}
                </div>

                <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded shrink-0">
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
