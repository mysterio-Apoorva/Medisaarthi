import React from 'react';
import { InterviewMessage } from '@/types';
import { Bot, User, Sparkles } from 'lucide-react';

interface ChatMessageProps {
  message: InterviewMessage;
  patientName?: string;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  patientName = 'Patient',
}) => {
  const isAI = message.sender === 'ai';

  return (
    <div
      className={`flex items-start gap-3.5 my-3 animate-in fade-in slide-in-from-bottom-2 duration-200 ${
        isAI ? 'justify-start' : 'justify-end'
      }`}
    >
      {/* AI Avatar */}
      {isAI && (
        <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-sky-600 to-teal-500 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5 ring-2 ring-sky-100">
          <Bot className="w-5 h-5" />
        </div>
      )}

      {/* Message Box */}
      <div
        className={`max-w-[85%] sm:max-w-[78%] rounded-2xl p-4 sm:p-5 transition-all shadow-xs ${
          isAI
            ? 'bg-white border border-slate-200/90 text-slate-800 rounded-tl-sm'
            : 'bg-sky-600 text-white rounded-tr-sm shadow-sky-600/10'
        }`}
      >
        <div className="flex items-center justify-between gap-4 mb-1">
          <span
            className={`text-[11px] font-bold uppercase tracking-wider ${
              isAI ? 'text-sky-700' : 'text-sky-100'
            }`}
          >
            {isAI ? 'Medisaarthi Assistant' : patientName}
          </span>
          <span
            className={`text-[10px] ${
              isAI ? 'text-slate-400' : 'text-sky-200'
            }`}
          >
            {message.timestamp}
          </span>
        </div>

        <p className={`text-base sm:text-[17px] leading-relaxed font-normal ${isAI ? 'text-slate-800' : 'text-white'}`}>
          {message.text}
        </p>

        {/* Extracted Information Chips beneath response */}
        {message.extracted_info && message.extracted_info.length > 0 && (
          <div
            className={`mt-3 pt-3 border-t flex flex-wrap items-center gap-1.5 ${
              isAI ? 'border-slate-100' : 'border-sky-500/50'
            }`}
          >
            <div
              className={`flex items-center gap-1 text-[11px] font-bold ${
                isAI ? 'text-teal-700' : 'text-teal-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Detected:</span>
            </div>
            {message.extracted_info.map((item, idx) => (
              <span
                key={idx}
                className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                  isAI
                    ? 'bg-teal-50 text-teal-800 border border-teal-200'
                    : 'bg-sky-700/80 text-white border border-sky-400/40'
                }`}
              >
                <span className="font-semibold opacity-85">{item.label}:</span>{' '}
                {item.value}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Patient Avatar */}
      {!isAI && (
        <div className="w-10 h-10 rounded-2xl bg-slate-700 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5 ring-2 ring-slate-100">
          <User className="w-5 h-5" />
        </div>
      )}
    </div>
  );
};
