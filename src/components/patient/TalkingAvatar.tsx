'use client';

type Props = { mouth: number; state: 'listening' | 'thinking' | 'speaking' | 'waiting'; language: 'en' | 'hi' };

export function TalkingAvatar({ mouth, state, language }: Props) {
  const labels = {
    listening: ['Listening to your microphone', 'आपकी बात सुन रहा हूँ'],
    thinking: ['Processing — please wait', 'कृपया प्रतीक्षा करें'],
    speaking: ['Speaking the current question', 'प्रश्न बोल रहा हूँ'],
    waiting: ['Ready when you are', 'आपका उत्तर सुनने के लिए तैयार'],
  };
  return <div className="flex items-center gap-4 rounded-2xl bg-gradient-to-br from-sky-50 to-teal-50 border border-sky-100 px-4 py-2" data-testid="talking-avatar" data-state={state}>
    <svg viewBox="0 0 160 164" className="h-36 w-32 shrink-0" role="img" aria-label="MediKiosk conversational assistant">
      <ellipse cx="80" cy="151" rx="48" ry="7" fill="#cbd5e1" opacity=".4" />
      <g className="avatar-idle">
        <path d="M29 150 Q29 103 80 105 Q131 103 131 150" fill="#0284c7" />
        <path d="M66 109 L80 129 L94 109" fill="#f0fdfa" />
        <rect x="71" y="94" width="18" height="22" rx="7" fill="#e8b58f" />
        <ellipse cx="80" cy="63" rx="43" ry="49" fill="#334155" />
        <ellipse cx="80" cy="69" rx="36" ry="42" fill="#f2c7a5" />
        <path d="M44 56 Q49 10 80 19 Q115 15 118 56 Q101 43 91 33 Q73 54 44 56" fill="#334155" />
        <g className="avatar-eyes" style={{ transformOrigin: '80px 67px' }}>
          <ellipse cx="65" cy="65" rx="4" ry="5" fill="#0f172a" />
          <ellipse cx="95" cy="65" rx="4" ry="5" fill="#0f172a" />
          <circle cx="66" cy="64" r="1.1" fill="white" /><circle cx="96" cy="64" r="1.1" fill="white" />
        </g>
        <path d="M78 70 L75 80 Q80 82 84 79" fill="none" stroke="#c58e6b" strokeWidth="2" strokeLinecap="round" />
        <ellipse data-testid="avatar-mouth" cx="80" cy="92" rx={state === 'speaking' ? 8 + mouth * 3 : 10} ry={state === 'speaking' ? 1.5 + mouth * 11 : 1.5} fill="#7f3541" />
        <path d="M39 61 Q28 63 34 85" stroke="#0d9488" strokeWidth="6" fill="none" strokeLinecap="round" />
        <path d="M34 81 Q40 96 60 97" stroke="#0d9488" strokeWidth="3" fill="none" />
        <rect x="57" y="94" width="10" height="6" rx="3" fill="#0d9488" />
      </g>
    </svg>
    <div><p className="font-bold text-sky-950">MediKiosk Assistant</p>
      <p role="status" className="mt-1 text-sm text-slate-600">{labels[state][language === 'hi' ? 1 : 0]}</p>
      <p className="mt-2 text-xs text-slate-500">{language === 'hi' ? 'डॉक्टर की समीक्षा के लिए आपकी जानकारी एकत्र करता है।' : 'Collecting your history for clinician review.'}</p>
    </div>
    <style jsx>{`
      .avatar-idle { animation: breathe 5s ease-in-out infinite; transform-origin: center bottom; }
      .avatar-eyes { animation: blink 6s infinite; }
      @keyframes breathe { 50% { transform: translateY(-2px); } }
      @keyframes blink { 0%, 44%, 48%, 100% { transform: scaleY(1); } 46% { transform: scaleY(.1); } }
      @media (prefers-reduced-motion: reduce) { .avatar-idle, .avatar-eyes { animation: none; } }
    `}</style>
  </div>;
}
