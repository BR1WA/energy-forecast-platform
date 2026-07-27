'use client';

import React, { useState, useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { alertsApi, API_BASE_URL } from '@/lib/api';
import { formatTimeAgo, cn } from '@/lib/utils';
import { useI18n } from '@/lib/i18n';
import { Bell, Search, X, LayoutDashboard, LineChart, AlertTriangle, Shield, Settings as SettingsIcon, Menu, Zap, CircleAlert } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { LogOut, Settings, User } from 'lucide-react';

export default function Navbar({ onMenuClick }: { onMenuClick?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { t, isRTL, language } = useI18n();

  // Search state
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Notifications state
  const [notifOpen, setNotifOpen] = useState(false);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const notifRef = useRef<HTMLDivElement>(null);

  const getPageTitle = () => {
    switch (pathname) {
      case '/dashboard':
        return t('nav.dashboard');
      case '/forecast':
        return t('forecast.title');
      case '/usage':
        return t('nav.consumption');
      case '/actions':
        return t('nav.recommendations');
      case '/simulation':
        return t('nav.simulation');
      case '/admin':
        return t('admin.title');
      case '/settings':
        return t('settings.title');
      default:
        return 'EnergyAI';
    }
  };

  const getPageDescription = () => {
    switch (pathname) {
      case '/dashboard':
        return t('dashboard.subtitle');
      case '/forecast':
        return t('forecast.subtitle');
      case '/usage':
        return 'Historical energy, estimated tariff cost, data quality, and CSV imports.';
      case '/actions':
        return 'Measured incidents and evidence-backed follow-up actions.';
      case '/simulation':
        return 'Explicitly controlled and clearly labelled demo readings.';
      case '/admin':
        return t('admin.subtitle');
      case '/settings':
        return t('settings.subtitle');
      default:
        return '';
    }
  };

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase() || 'U';

  useEffect(() => {
    const loadAlerts = async () => {
      try {
        const data = await alertsApi.getAlerts();
        setAlerts(data.slice(0, 8));
        setUnreadCount(data.filter((a: any) => !a.is_read).length);
      } catch {
        // silently fail if not authenticated
      }
    };
    void loadAlerts();
    const timer = window.setInterval(() => void loadAlerts(), 30_000);
    return () => window.clearInterval(timer);
  }, [router]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setSearchOpen(false);
        setNotifOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    if (searchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setSearchQuery('');
    }
  }, [searchOpen]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const searchPages = [
    { name: t('nav.dashboard'), path: '/dashboard', icon: LayoutDashboard, description: language === 'ar' ? 'بيانات القياس والتحميل المباشر للعداد الذكي' : language === 'fr' ? 'Télémesures et puissances du compteur en temps réel' : 'Real-time smart meter telemetry and load rates' },
    { name: t('nav.forecasts'), path: '/forecast', icon: LineChart, description: t('forecast.subtitle') },
    { name: t('nav.consumption'), path: '/usage', icon: Zap, description: 'Historical energy, tariff estimates, and CSV imports' },
    { name: t('nav.recommendations'), path: '/actions', icon: CircleAlert, description: 'Incidents and evidence-backed follow-up actions' },
    { name: t('nav.settings'), path: '/settings', icon: SettingsIcon, description: t('settings.subtitle') },
    ...(user?.role === 'admin'
      ? [{ name: t('nav.admin'), path: '/admin', icon: Shield, description: t('admin.subtitle') }]
      : []),
  ];

  const filteredPages = searchPages.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleNavigate = (path: string) => {
    router.push(path);
    setSearchOpen(false);
  };

  const handleAcknowledge = async (alertId: string) => {
    try {
      await alertsApi.acknowledgeAlert(alertId);
      setAlerts((prev) => prev.map((a) => a.id === alertId ? { ...a, is_read: true } : a));
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to acknowledge alert', err);
    }
  };

  const severityColors: Record<string, string> = {
    critical: 'text-red-400 bg-red-500/10',
    high: 'text-orange-400 bg-orange-500/10',
    medium: 'text-amber-400 bg-amber-500/10',
    low: 'text-blue-400 bg-blue-500/10',
  };

  const timeAgo = formatTimeAgo;

  return (
    <header
      id="navbar"
      className="sticky top-0 z-30 h-16 flex items-center justify-between gap-3 px-4 sm:px-6 border-b border-white/[0.06] bg-[#0A0F1C]/60 backdrop-blur-xl"
    >
      <div className="flex min-w-0 items-center gap-3">
        <button aria-label="Open navigation" className="rounded-md p-1.5 text-slate-400 hover:bg-white/5 hover:text-white md:hidden" onClick={onMenuClick} type="button"><Menu className="h-5 w-5" /></button>
        <div className="min-w-0">
        <h2 className="truncate text-base font-semibold text-white sm:text-lg">{getPageTitle()}</h2>
        {getPageDescription() && (
          <p className="hidden truncate text-xs text-slate-400 sm:block">{getPageDescription()}</p>
        )}
        </div>
      </div>

      <div className="hidden flex-1 lg:block" />

      <div className="flex items-center gap-2 sm:gap-3">
        <div className="relative" ref={searchRef}>
          <button
            id="navbar-search"
            onClick={() => setSearchOpen(!searchOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.06] transition-all duration-200 text-sm"
          >
            <Search className="w-4 h-4" />
            <span className="hidden md:inline">{isRTL ? 'بحث...' : 'Search...'}</span>
            <kbd className="hidden md:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] font-mono text-slate-500">
              Ctrl+K
            </kbd>
          </button>

          {searchOpen && (
            <div className={cn(
              "absolute top-full mt-2 w-80 bg-[#111827] border border-white/10 rounded-xl shadow-2xl shadow-black/40 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200",
              isRTL ? "left-0" : "right-0"
            )}>
              <div className="flex items-center gap-2 p-3 border-b border-white/[0.06]">
                <Search className="w-4 h-4 text-slate-500 shrink-0" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={isRTL ? 'البحث في الصفحات...' : 'Search pages...'}
                  className="flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 outline-none"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && filteredPages.length > 0) {
                      handleNavigate(filteredPages[0].path);
                    }
                  }}
                />
                <button onClick={() => setSearchOpen(false)} className="text-slate-500 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto py-1">
                {filteredPages.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-4">{isRTL ? 'لم يتم العثور على نتائج' : 'No results found'}</p>
                ) : (
                  filteredPages.map((page) => (
                    <button
                      key={page.path}
                      onClick={() => handleNavigate(page.path)}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-white/[0.04] transition-colors ${
                        pathname === page.path ? 'bg-blue-500/10' : ''
                      }`}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        pathname === page.path ? 'bg-blue-500/20' : 'bg-white/[0.04]'
                      }`}>
                        <page.icon className={`w-4 h-4 ${pathname === page.path ? 'text-blue-400' : 'text-slate-400'}`} />
                      </div>
                      <div>
                        <p className={`text-sm font-medium ${pathname === page.path ? 'text-blue-400' : 'text-white'}`}>
                          {page.name}
                        </p>
                        <p className="text-[11px] text-slate-500">{page.description}</p>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <div className="relative" ref={notifRef}>
          <button
            id="navbar-notifications"
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all duration-200"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <Badge
                className="absolute -top-0.5 -right-0.5 w-4 h-4 p-0 flex items-center justify-center text-[9px] bg-blue-500 border-0 text-white"
              >
                {unreadCount > 9 ? '9+' : unreadCount}
              </Badge>
            )}
          </button>

          {/* Notifications Dropdown */}
          {notifOpen && (
            <div className={cn(
              "absolute top-full mt-2 w-96 bg-[#111827] border border-white/10 rounded-xl shadow-2xl shadow-black/40 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200",
              isRTL ? "left-0" : "right-0"
            )}>
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
                <h3 className="text-sm font-semibold text-white">{isRTL ? 'الإشعارات' : 'Notifications'}</h3>
                {unreadCount > 0 && (
                  <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-[10px]">
                    {unreadCount} {isRTL ? 'غير مقروءة' : 'unread'}
                  </Badge>
                )}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {alerts.length === 0 ? (
                  <div className="py-8 text-center">
                    <Bell className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                    <p className="text-sm text-slate-500">{isRTL ? 'لا توجد إشعارات' : 'No notifications'}</p>
                  </div>
                ) : (
                  alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className={`flex items-start gap-3 px-4 py-3 border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${
                        !alert.is_read ? 'bg-blue-500/[0.03]' : ''
                      }`}
                    >
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${severityColors[alert.severity] || severityColors.medium}`}>
                        <AlertTriangle className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-medium text-white truncate">{alert.title}</p>
                          <span className="text-[10px] text-slate-500 shrink-0">{timeAgo(alert.created_at)}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-2">{alert.message}</p>
                        {!alert.is_read && (
                          <button
                            onClick={() => handleAcknowledge(alert.id)}
                            className="text-[10px] text-blue-400 hover:text-blue-300 mt-1 font-medium"
                          >
                            {isRTL ? 'تحديد كمقروء' : 'Mark as read'}
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
              <button
                onClick={() => { router.push('/actions'); setSearchOpen(false); setNotifOpen(false); }}
                className="w-full px-4 py-2.5 text-xs text-center text-blue-400 hover:text-blue-300 hover:bg-white/[0.02] border-t border-white/[0.06] font-medium transition-colors"
              >
                {isRTL ? 'عرض جميع الإجراءات ←' : 'View all actions →'}
              </button>
            </div>
          )}
        </div>

        {/* User Avatar */}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <button
                id="navbar-user-menu"
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/[0.04] transition-all duration-200"
              />
            }
          >
              <Avatar className="w-8 h-8 ring-2 ring-blue-500/20">
                {user?.avatar_url && (
                  <AvatarImage
                    src={user.avatar_url.startsWith('http') ? user.avatar_url : `${API_BASE_URL}${user.avatar_url}`}
                    alt={user?.full_name}
                    className="object-cover"
                  />
                )}
                <AvatarFallback className="bg-gradient-to-br from-blue-600 to-cyan-500 text-white text-xs font-semibold">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="hidden md:block text-left">
                <p className="text-sm font-medium text-white">
                  {user?.full_name || 'User'}
                </p>
                <p className="text-[10px] text-slate-500 capitalize">
                  {user?.role || 'user'}
                </p>
              </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-56 bg-[#111827] border-white/10"
          >
            <div className="px-3 py-2">
              <p className="text-sm font-medium text-white">
                {user?.full_name}
              </p>
              <p className="text-xs text-slate-400">{user?.email}</p>
            </div>
            <DropdownMenuSeparator className="bg-white/[0.06]" />
            <DropdownMenuItem
              id="nav-profile"
              className="text-slate-300 focus:text-white focus:bg-white/[0.06] cursor-pointer p-0"
            >
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => router.push('/settings?tab=security')}>
                <User className="w-4 h-4 mr-2" />
                Account security
              </div>
            </DropdownMenuItem>
            <DropdownMenuItem
              id="nav-settings"
              className="text-slate-300 focus:text-white focus:bg-white/[0.06] cursor-pointer p-0"
            >
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => router.push('/settings')}>
                <Settings className="w-4 h-4 mr-2" />
                {t('nav.settings')}
              </div>
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-white/[0.06]" />
            <DropdownMenuItem
              id="nav-logout"
              className="text-red-400 focus:text-red-300 focus:bg-red-500/10 cursor-pointer p-0"
            >
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => logout()}>
                <LogOut className="w-4 h-4 mr-2" />
                {t('nav.logout')}
              </div>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
