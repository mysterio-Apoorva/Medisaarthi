'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  HeartPulse,
  LayoutDashboard,
  Users,
  ShieldCheck,
  UserCheck,
  LogOut,
  Stethoscope,
} from 'lucide-react';

export const DoctorSidebar: React.FC = () => {
  const pathname = usePathname();

  const navItems = [
    {
      label: 'Dashboard',
      href: '/doctor',
      icon: LayoutDashboard,
      active: pathname === '/doctor',
    },
    {
      label: 'Patients',
      href: '/doctor#patients-section',
      icon: Users,
      active: pathname.startsWith('/doctor/patients'),
    },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-100 flex flex-col justify-between shrink-0 border-r border-slate-800 min-h-screen">
      <div>
        {/* Brand Header */}
        <div className="p-6 border-b border-slate-800/80">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-sky-500 flex items-center justify-center text-slate-950 font-black shadow-md group-hover:bg-sky-400 transition-colors">
              <HeartPulse className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white tracking-tight text-base leading-none">
                  MEDISAARTHI
                </span>
              </div>
              <p className="text-[11px] text-sky-400 font-semibold tracking-wider uppercase mt-1 leading-none">
                Clinical Intelligence
              </p>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1.5">
          <div className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Clinical Workspace
          </div>
          {navItems.map((item, idx) => {
            const Icon = item.icon;
            return (
              <Link
                key={idx}
                href={item.href}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  item.active
                    ? 'bg-sky-600 text-white shadow-sm font-semibold'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${item.active ? 'text-white' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
              </Link>
            );
          })}

          <div className="pt-4 mt-4 border-t border-slate-800">
            <div className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Quick Switch
            </div>
            <Link
              href="/patient"
              className="flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold text-emerald-400 hover:bg-slate-800 transition-colors"
            >
              <UserCheck className="w-4 h-4 text-emerald-400" />
              <span>Launch Patient App</span>
            </Link>
          </div>
        </nav>
      </div>

      {/* Doctor Profile Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40">
        <div className="flex items-center gap-3 p-2 rounded-xl bg-slate-800/60 border border-slate-700/60">
          <div className="w-10 h-10 rounded-xl bg-sky-600/30 text-sky-300 border border-sky-500/30 flex items-center justify-center font-bold text-sm shrink-0">
            DR
          </div>
          <div className="overflow-hidden">
            <div className="font-semibold text-xs text-white truncate">
              Authenticated clinician
            </div>
            <div className="text-[11px] text-slate-400 truncate">
              Assigned patient workspace
            </div>
          </div>
        </div>
        <div className="mt-2 text-center">
          <Link
            href="/doctor/login"
            className="inline-flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
          >
            <LogOut className="w-3 h-3" />
            <span>Sign Out / Switch Doctor</span>
          </Link>
        </div>
      </div>
    </aside>
  );
};
