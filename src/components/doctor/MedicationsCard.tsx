import React from 'react';
import { Medication } from '@/types';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Pill, Clock } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';

interface MedicationsCardProps {
  medications: Medication[];
}

export const MedicationsCard: React.FC<MedicationsCardProps> = ({ medications }) => {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-800">
          <Pill className="w-4 h-4 text-sky-600" />
          <span>Current Active Medications</span>
        </CardTitle>
        <Badge variant="primary" size="sm">
          {medications.length} Prescriptions
        </Badge>
      </CardHeader>
      <CardContent>
        {medications.length === 0 ? (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 text-xs text-slate-500 italic text-center">
            No active regular medications reported.
          </div>
        ) : (
          <div className="space-y-3">
            {medications.map((med, idx) => (
              <div
                key={med.id || idx}
                className="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200/80 flex items-start justify-between gap-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-slate-900">
                      {med.name}
                    </span>
                    <span className="text-xs font-mono font-bold bg-white border border-slate-200 text-slate-700 px-2 py-0.5 rounded">
                      {med.dosage}
                    </span>
                  </div>

                  {med.frequency && (
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-1">
                      <Clock className="w-3 h-3 text-slate-400" />
                      <span>{med.frequency}</span>
                    </div>
                  )}

                  {med.purpose && (
                    <div className="text-[11px] text-slate-600 mt-0.5">
                      Indication: <span className="font-medium text-slate-800">{med.purpose}</span>
                    </div>
                  )}
                </div>

                <Badge variant="neutral" size="sm">
                  Active
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
