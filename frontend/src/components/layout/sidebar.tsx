'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';
import {
  LayoutDashboard,
  LineChart,
  BarChart3,
  Bell,
  ChevronLeft,
  ChevronRight,
  Zap,
  LogOut,
  Settings,
  User,
  Cpu,
  Sparkles,
  Target,
  FileText,
  Shield,
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

import { API_BASE_URL } from '@/lib/api';

interface NavItem {
  label: string;
  translationKey: string;
  href: string;
  icon: any;
  adminOnly?: boolean;
  disabled?: boolean;
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    translationKey: 'nav.dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    label: 'Energy Analytics',
    translationKey: 'nav.consumption',
    href: '/consumption',
    icon: Zap,
  },
  {
    label: 'Forecast Center',
    translationKey: 'nav.forecasts',
    href: '/forecast',
    icon: LineChart,
  },
  {
    label: 'AI Recommendations',
    translationKey: 'nav.recommendations',
    href: '/recommendations',
    icon: Sparkles,
  },
  {
    label: 'Budget & Goals',
    translationKey: 'nav.budget',
    href: '/budget',
    icon: Target,
  },
  {
    label: 'Reports',
    translationKey: 'nav.reports',
    href: '/reports',
    icon: FileText,
  },
  {
    label: 'Virtual House',
    translationKey: 'nav.simulation',
    href: '/simulation',
    icon: BarChart3,
  },
  {
    label: 'Notifications',
    translationKey: 'nav.alerts',
    href: '/alerts',
    icon: Bell,
  },
  {
    label: 'Models',
    translationKey: 'nav.models',
    href: '/models',
    icon: Cpu,
  },
  {
    label: 'Admin Panel',
    translationKey: 'nav.admin',
    href: '/admin',
    icon: Shield,
    adminOnly: true,
  },
  {
    label: 'Settings',
    translationKey: 'nav.settings',
    href: '/settings',
    icon: Settings,
  },
];

interface SidebarProps {
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}

export default function Sidebar({ collapsed, setCollapsed }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { t, isRTL } = useI18n();

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase() || 'U';

  return (
    <aside
      id="sidebar"
      className={cn(
        'fixed top-0 z-40 h-screen flex flex-col transition-all duration-300 ease-in-out',
        'bg-[#0d1321]/80 backdrop-blur-2xl',
        isRTL ? 'right-0 border-l border-white/[0.06]' : 'left-0 border-r border-white/[0.06]',
        collapsed ? 'w-[72px]' : 'w-[260px]'
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 shadow-lg shadow-blue-500/20 shrink-0">
            <Zap className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden animate-in fade-in slide-in-from-left-2 duration-300">
              <h1 className="text-base font-bold text-white tracking-tight truncate">
                EnergyAI
              </h1>
              <p className="text-[10px] text-slate-400 -mt-0.5">
                {isRTL ? 'منصة إدارة الطاقة' : 'Management Platform'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems
          .filter((item) => {
            if (item.adminOnly && user?.role !== 'admin') return false;
            return true;
          })
          .map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.disabled ? '#' : item.href}
                id={`nav-${item.label.toLowerCase()}`}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group relative',
                  isActive
                    ? 'bg-blue-500/15 text-blue-400'
                    : 'text-slate-400 hover:text-white hover:bg-white/[0.04]',
                  item.disabled && 'opacity-50 cursor-not-allowed pointer-events-none'
                )}
              >
                {isActive && (
                  <div className={cn(
                    'absolute top-1/2 -translate-y-1/2 w-[3px] h-5 bg-blue-400',
                    isRTL ? 'right-0 rounded-l-full' : 'left-0 rounded-r-full'
                  )} />
                )}
                <item.icon
                  className={cn(
                    'w-5 h-5 shrink-0 transition-colors duration-200',
                    isActive
                      ? 'text-blue-400'
                      : 'text-slate-500 group-hover:text-slate-300'
                  )}
                />
                {!collapsed && (
                  <span className="truncate animate-in fade-in slide-in-from-left-2 duration-200">
                    {t(item.translationKey)}
                  </span>
                )}
                {item.disabled && !collapsed && (
                  <span className="ml-auto text-[9px] uppercase tracking-wider bg-white/10 text-slate-400 px-1.5 py-0.5 rounded">
                    Soon
                  </span>
                )}
                {isActive && !collapsed && (
                  <div className={cn(
                    'absolute w-1.5 h-1.5 rounded-full bg-blue-400 shadow-sm shadow-blue-400/50',
                    isRTL ? 'left-3' : 'right-3'
                  )} />
                )}
              </Link>
            );
          })}
      </nav>

      {/* Bottom Section */}
      <div className="px-3 pb-4 space-y-2 border-t border-white/[0.06] pt-4">
        {/* Collapse Button */}
        <button
          id="sidebar-collapse-btn"
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center w-full py-2 rounded-lg text-slate-500 hover:text-white hover:bg-white/[0.04] transition-all duration-200"
        >
          {collapsed ? (
            isRTL ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
          ) : (
            isRTL ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />
          )}
        </button>

        {/* User Profile */}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <button
                id="sidebar-user-menu"
                className={cn(
                  'flex items-center w-full gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
                  'hover:bg-white/[0.04] text-left'
                )}
              />
            }
          >
              <Avatar className="w-8 h-8 shrink-0 ring-2 ring-blue-500/20">
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
              {!collapsed && (
                <div className="min-w-0 animate-in fade-in duration-200">
                  <p className="text-sm font-medium text-white truncate">
                    {user?.full_name || 'User'}
                  </p>
                  <p className="text-xs text-slate-500 truncate">
                    {user?.email || ''}
                  </p>
                </div>
              )}
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            side="top"
            className="w-56 bg-[#111827] border-white/10"
          >
            <DropdownMenuItem
              id="menu-profile"
              className="text-slate-300 focus:text-white focus:bg-white/[0.06] cursor-pointer p-0"
            >
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => router.push('/profile')}>
                <User className="w-4 h-4 mr-2" />
                {t('nav.profile')}
              </div>
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-white/[0.06]" />
            <DropdownMenuItem
              id="menu-settings"
              className="text-slate-300 focus:text-white focus:bg-white/[0.06] cursor-pointer p-0"
            >
              <div className="w-full h-full flex items-center px-3 py-2" onClick={() => router.push('/settings')}>
                <Settings className="w-4 h-4 mr-2" />
                {t('nav.settings')}
              </div>
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-white/[0.06]" />
            <DropdownMenuItem
              id="menu-logout"
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
    </aside>
  );
}
