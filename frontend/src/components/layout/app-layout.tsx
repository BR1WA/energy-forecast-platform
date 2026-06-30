'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from './sidebar';
import Navbar from './navbar';
import { useI18n } from '@/lib/i18n';
import { DataModeProvider } from '@/contexts/DataModeContext';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { isRTL } = useI18n();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#0A0F1C]" suppressHydrationWarning>
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-2 border-blue-500/20" />
            <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin" />
          </div>
          <p className="text-sm text-slate-400 animate-pulse">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const marginClass = isRTL
    ? (sidebarCollapsed ? 'mr-[72px]' : 'mr-[260px]')
    : (sidebarCollapsed ? 'ml-[72px]' : 'ml-[260px]');

  return (
    <DataModeProvider>
      <div className="flex h-screen bg-[#0A0F1C] overflow-hidden" suppressHydrationWarning>
        <Sidebar collapsed={sidebarCollapsed} setCollapsed={setSidebarCollapsed} />
        <div className={`flex flex-col flex-1 transition-all duration-300 ${marginClass}`}>
          <Navbar />
          <main className="flex-1 overflow-y-auto p-6">
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              {children}
            </div>
          </main>
        </div>
      </div>
    </DataModeProvider>
  );
}
