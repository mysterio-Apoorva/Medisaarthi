import React from 'react';
import { Drawer } from '@/components/ui/Modal';
import { InterviewMessage, Patient } from '@/types';
import { Bot, User, Sparkles, Clock, MessageSquare } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';

interface InterviewDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  patient: Pick<Patient, 'patient_id' | 'name'> & {language?: string};
  transcript: InterviewMessage[];
}

export const InterviewDrawer: React.FC<InterviewDrawerProps> = ({
  isOpen,
  onClose,
  patient,
  transcript,
}) => {
  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-sky-600" />
          <span>Pre-Consultation Interview Transcript</span>
        </div>
      }
      subtitle={`Complete dialogue session for ${patient.name} (#${patient.patient_id})`}
      width="xl"
    >
      <div className="space-y-4">
        {/* Top Session Metadata */}
        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700">Language:</span>
            <Badge variant="primary" size="sm">
              {patient.language === 'hi' ? 'Hindi (हिंदी)' : 'English'}
            </Badge>
          </div>
          <div className="flex items-center gap-1.5 text-slate-500 font-medium">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>{transcript.length} dialogue turns</span>
          </div>
        </div>

        {/* Transcript Conversation Flow */}
        <div className="space-y-3 pt-2">
          {transcript.map((msg, idx) => {
            const isAI = msg.sender === 'ai';
            return (
              <div
                key={msg.id || idx}
                className={`p-4 rounded-2xl border transition-all ${
                  isAI
                    ? 'bg-sky-50/50 border-sky-100 text-slate-900 ml-0 mr-6'
                    : 'bg-white border-slate-200 text-slate-900 ml-6 mr-0 shadow-2xs'
                }`}
              >
                {/* Header */}
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${
                        isAI ? 'bg-sky-600 text-white' : 'bg-slate-700 text-white'
                      }`}
                    >
                      {isAI ? <Bot className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                    </div>
                    <span className="font-bold text-xs text-slate-800">
                      {isAI ? 'Medisaarthi AI Assistant' : patient.name}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono">
                    {msg.timestamp}
                  </span>
                </div>

                {/* Body */}
                <p className="text-sm text-slate-800 leading-relaxed font-normal pl-8">
                  {msg.text}
                </p>

                {/* Extracted badges if any */}
                {msg.extracted_info && msg.extracted_info.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-100 pl-8 flex flex-wrap gap-1.5">
                    <div className="flex items-center gap-1 text-[10px] font-bold text-teal-700">
                      <Sparkles className="w-3 h-3" />
                      <span>Extracted:</span>
                    </div>
                    {msg.extracted_info.map((info, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-teal-50 border border-teal-200 text-teal-800 text-[11px] font-medium"
                      >
                        <strong>{info.label}:</strong> {info.value}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Drawer>
  );
};
