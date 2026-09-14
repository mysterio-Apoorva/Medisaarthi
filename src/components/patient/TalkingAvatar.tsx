'use client';

type Props = { mouth: number; state: 'listening' | 'thinking' | 'speaking' | 'waiting' | 'error'; language: 'en' | 'hi'; immersive?: boolean };

export function TalkingAvatar({ mouth, state, language, immersive = false }: Props) {
  const labels = {
    error: ['We can take a moment', 'हम थोड़ा रुक सकते हैं'],
    listening: ['Listening to your microphone', 'आपकी बात सुन रहा हूँ'],
    thinking: ['Processing — please wait', 'कृपया प्रतीक्षा करें'],
    speaking: ['Speaking the current question', 'प्रश्न बोल रहा हूँ'],
    waiting: ['Ready when you are', 'आपका उत्तर सुनने के लिए तैयार'],
  };
  return <div className={immersive ? 'avatar-stage flex h-full w-full items-end justify-center' : 'flex items-center gap-4 rounded-2xl bg-gradient-to-br from-sky-50 to-teal-50 border border-sky-100 px-4 py-2'} data-testid="talking-avatar" data-state={state}>
    <svg viewBox="0 0 160 164" className={immersive ? 'h-full max-h-[64dvh] w-auto max-w-full drop-shadow-xl' : 'h-36 w-32 shrink-0'} role="img" aria-label={language === 'hi' ? 'मेडीकियोस्क सहायक' : 'MediKiosk conversational assistant'}>
      <defs>
        <radialGradient id="skin"><stop stopColor="#f6d4b7"/><stop offset="1" stopColor="#dca67f"/></radialGradient>
        <linearGradient id="coat" x2="1" y2="1"><stop stopColor="#ffffff"/><stop offset="1" stopColor="#cce5e6"/></linearGradient>
        <linearGradient id="hair" x2="1" y2="1"><stop stopColor="#493e3b"/><stop offset="1" stopColor="#262b35"/></linearGradient>
      </defs>
      <ellipse cx="80" cy="151" rx="48" ry="7" fill="#cbd5e1" opacity=".4" />
      <g className="avatar-idle">
        <path d="M22 164 Q20 113 64 109 L96 109 Q140 113 138 164" fill="url(#coat)" />
        <path d="M62 110 L80 126 L98 110 L92 164 L68 164" fill="#217b83" />
        <path d="M62 109 L55 132 L68 137 L62 146 L71 164 M98 109 L105 132 L92 137 L98 146 L89 164" fill="none" stroke="#b1d0d0" strokeWidth="1.5" />
        <rect x="71" y="94" width="18" height="22" rx="7" fill="#e8b58f" />
        <g className={`avatar-head ${state}`}>
        <ellipse cx="80" cy="63" rx="40" ry="48" fill="url(#hair)" />
        <ellipse cx="44" cy="73" rx="5" ry="9" fill="#dca67f"/><ellipse cx="116" cy="73" rx="5" ry="9" fill="#dca67f"/>
        <ellipse cx="80" cy="69" rx="36" ry="42" fill="url(#skin)" />
        <path d="M44 56 Q49 10 80 19 Q115 15 118 56 Q101 43 91 33 Q73 54 44 56" fill="url(#hair)" />
        <path d="M55 55 Q64 50 72 55 M88 55 Q96 50 105 55" fill="none" stroke="#5c443a" strokeWidth="2" strokeLinecap="round"/>
        <ellipse cx="57" cy="81" rx="8" ry="4" fill="#dd9d8b" opacity=".28"/><ellipse cx="103" cy="81" rx="8" ry="4" fill="#dd9d8b" opacity=".28"/>
        <g className="avatar-eyes" style={{ transformOrigin: '80px 67px' }}>
          <ellipse cx="65" cy="65" rx="4" ry="5" fill="#0f172a" />
          <ellipse cx="95" cy="65" rx="4" ry="5" fill="#0f172a" />
          <circle cx="66" cy="64" r="1.1" fill="white" /><circle cx="96" cy="64" r="1.1" fill="white" />
        </g>
        <path d="M78 70 L75 80 Q80 82 84 79" fill="none" stroke="#c58e6b" strokeWidth="2" strokeLinecap="round" />
        <ellipse data-testid="avatar-mouth" cx="80" cy="92" rx={state === 'speaking' ? 8 + mouth * 3 : 10} ry={state === 'speaking' ? 1.5 + mouth * 11 : 1.5} fill="#7f3541" />
        {state === 'speaking' && mouth > .12 && <path d="M74 90 Q80 92 86 90" fill="none" stroke="#fff5e9" strokeWidth="2"/>}
        <path d="M68 91 Q80 99 92 91" fill="none" stroke="#b57867" strokeWidth=".8"/>
        <path d="M39 61 Q28 63 34 85" stroke="#0d9488" strokeWidth="6" fill="none" strokeLinecap="round" />
        <path d="M34 81 Q40 96 60 97" stroke="#0d9488" strokeWidth="3" fill="none" />
        <rect x="57" y="94" width="10" height="6" rx="3" fill="#0d9488" />
        </g>
      </g>
    </svg>
    <div className={immersive ? 'sr-only' : ''}><p className="font-bold text-sky-950">MediKiosk Assistant</p>
      <p role="status" className="mt-1 text-sm text-slate-600">{labels[state][language === 'hi' ? 1 : 0]}</p>
      <p className="mt-2 text-xs text-slate-500">{language === 'hi' ? 'डॉक्टर की समीक्षा के लिए आपकी जानकारी एकत्र करता है।' : 'Collecting your history for clinician review.'}</p>
    </div>
    <style jsx>{`
      .avatar-idle { animation: breathe 5s ease-in-out infinite; transform-origin: center bottom; }
      .avatar-eyes { animation: blink 6s infinite; }
      .avatar-head { transform-origin: 80px 105px; animation: settle 9s ease-in-out infinite; }
      .avatar-head.listening { animation: attentive 4s ease-in-out infinite; }
      .avatar-head.thinking { animation: thoughtful 3s ease-in-out infinite; }
      .avatar-head.speaking { animation: talking 3.4s ease-in-out infinite; }
      @keyframes settle { 35% { transform: rotate(-1deg); } 70% { transform: rotate(1deg); } }
      @keyframes attentive { 50% { transform: rotate(-2deg) translateY(1px); } }
      @keyframes thoughtful { 50% { transform: rotate(2deg) translateX(1px); } }
      @keyframes talking { 30% { transform: rotate(-.8deg); } 70% { transform: translateY(-.8px) rotate(.8deg); } }
      @keyframes breathe { 50% { transform: translateY(-2px); } }
      @keyframes blink { 0%, 44%, 48%, 100% { transform: scaleY(1); } 46% { transform: scaleY(.1); } }
      @media (prefers-reduced-motion: reduce) { .avatar-idle, .avatar-eyes, .avatar-head { animation: none !important; } }
    `}</style>
  </div>;
}
