import React from 'react';

export function MediKioskLogo({ className = 'h-10 w-10', title = 'MediKiosk' }: { className?: string; title?: string }) {
  return <svg viewBox="0 0 64 64" role="img" aria-label={title} className={className}>
    <title>{title}</title>
    <defs><linearGradient id="medikiosk-gradient" x1="9" y1="7" x2="56" y2="59" gradientUnits="userSpaceOnUse"><stop stopColor="#0284c7" /><stop offset="1" stopColor="#0d9488" /></linearGradient></defs>
    <rect x="5" y="5" width="54" height="54" rx="18" fill="url(#medikiosk-gradient)" />
    <path d="M18 21.5c0-3.04 2.46-5.5 5.5-5.5H39l8 8v16.5A5.5 5.5 0 0 1 41.5 46h-18a5.5 5.5 0 0 1-5.5-5.5v-19Z" fill="white" fillOpacity=".96" />
    <path d="M39 18.2V24h5.8" fill="none" stroke="#0d9488" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M22 34h5l2.7-5.2 4.1 10 2.7-4.8H43" fill="none" stroke="#0284c7" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="23" cy="25.2" r="2.7" fill="#0d9488" />
  </svg>;
}
