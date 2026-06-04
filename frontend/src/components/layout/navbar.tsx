'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { alertsApi } from '@/lib/api';
import { Bell, Search, X, LayoutDashboard, LineChart, BarChart3, AlertTriangle, Shield, Settings as SettingsIcon } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { LogOut, Settings, User } from 'lucide-react';

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/forecast': 'Forecaster',
  '/analytics': 'Analytics',
  '/alerts': 'Alerts',
  '/admin': 'Admin Panel',
  '/settings': 'Settings',
};

const pageDescriptions: Record<string, string> = {
  '/dashboard': 'Monitor your energy consumption overview',
  '/forecast': 'Run predictive models on your data',
  '/analytics': 'Explore historical trends and insights',
  '/alerts': 'Manage alerts and thresholds',
  '/admin': 'System administration and management',
  '/settings': 'Manage your account preferences',
};

// Search items
const searchPages = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, description: 'Energy overview & stats' },
  { name: 'Forecaster', path: '/forecast', icon: LineChart, description: 'Run ML predictions' },
  { name: 'Analytics', path: '/analytics', icon: BarChart3, description: 'Historical trends' },
  { name: 'Alerts', path: '/alerts', icon: AlertTriangle, description: 'Alert management' },
  { name: 'Admin Panel', path: '/admin', icon: Shield, description: 'User & system management' },
  { name: 'Settings', path: '/settings', icon: SettingsIcon, description: 'Account preferences' },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

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

  const title = pageTitles[pathname] || 'EnergyAI';
  const description = pageDescriptions[pathname] || '';

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase() || 'U';

  // Load alerts
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
    loadAlerts();
    const interval = setInterval(loadAlerts, 30000);
    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcut ⌘K / Ctrl+K
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

  // Focus search input when opened
  useEffect(() => {
    if (searchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setSearchQuery('');
    }
  }, [searchOpen]);

  // Click outside to close
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

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <header
      id="navbar"
      className="sticky top-0 z-30 h-16 flex items-center justify-between px-6 border-b border-white/[0.06] bg-[#0A0F1C]/60 backdrop-blur-xl"
    >
      {/* Left: Page Title */}
      <div>
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {description && (
          <p className="text-xs text-slate-400 -mt-0.5">{description}</p>
        )}
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="relative" ref={searchRef}>
          <button
            id="navbar-search"
            onClick={() => setSearchOpen(!searchOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.06] transition-all duration-200 text-sm"
          >
            <Search className="w-4 h-4" />
            <span className="hidden md:inline">Search...</span>
            <kbd className="hidden md:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] font-mono text-slate-500">
              ⌘K
            </kbd>
          </button>

          {/* Search Dropdown */}
          {searchOpen && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-[#111827] border border-white/10 rounded-xl shadow-2xl shadow-black/40 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="flex items-center gap-2 p-3 border-b border-white/[0.06]">
                <Search className="w-4 h-4 text-slate-500 shrink-0" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search pages..."
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
                  <p className="text-sm text-slate-500 text-center py-4">No results found</p>
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

        {/* Notifications */}
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
            <div className="absolute right-0 top-full mt-2 w-96 bg-[#111827] border border-white/10 rounded-xl shadow-2xl shadow-black/40 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
                <h3 className="text-sm font-semibold text-white">Notifications</h3>
                {unreadCount > 0 && (
                  <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-[10px]">
                    {unreadCount} unread
                  </Badge>
                )}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {alerts.length === 0 ? (
                  <div className="py-8 text-center">
                    <Bell className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                    <p className="text-sm text-slate-500">No notifications</p>
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
                            Mark as read
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
              <button
                onClick={() => { router.push('/alerts'); setNotifOpen(false); }}
                className="w-full px-4 py-2.5 text-xs text-center text-blue-400 hover:text-blue-300 hover:bg-white/[0.02] border-t border-white/[0.06] font-medium transition-colors"
              >
                View all alerts →
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
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => router.push('/settings')}>
                <User className="w-4 h-4 mr-2" />
                Profile
              </div>
            </DropdownMenuItem>
            <DropdownMenuItem
              id="nav-settings"
              className="text-slate-300 focus:text-white focus:bg-white/[0.06] cursor-pointer p-0"
            >
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => router.push('/settings')}>
                <Settings className="w-4 h-4 mr-2" />
                Settings
              </div>
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-white/[0.06]" />
            <DropdownMenuItem
              id="nav-logout"
              className="text-red-400 focus:text-red-300 focus:bg-red-500/10 cursor-pointer p-0"
            >
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => logout()}>
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </div>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
