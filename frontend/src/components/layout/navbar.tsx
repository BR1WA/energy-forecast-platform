'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Bell, Search } from 'lucide-react';
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
};

const pageDescriptions: Record<string, string> = {
  '/dashboard': 'Monitor your energy consumption overview',
  '/forecast': 'Run predictive models on your data',
  '/analytics': 'Explore historical trends and insights',
  '/alerts': 'Manage alerts and thresholds',
  '/admin': 'System administration and management',
};

export default function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const title = pageTitles[pathname] || 'EnergyAI';
  const description = pageDescriptions[pathname] || '';

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase() || 'U';

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
        <button
          id="navbar-search"
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.06] transition-all duration-200 text-sm"
        >
          <Search className="w-4 h-4" />
          <span className="hidden md:inline">Search...</span>
          <kbd className="hidden md:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] font-mono text-slate-500">
            ⌘K
          </kbd>
        </button>

        {/* Notifications */}
        <button
          id="navbar-notifications"
          className="relative p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all duration-200"
        >
          <Bell className="w-5 h-5" />
          <Badge
            className="absolute -top-0.5 -right-0.5 w-4 h-4 p-0 flex items-center justify-center text-[9px] bg-blue-500 border-0 text-white"
          >
            3
          </Badge>
        </button>

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
              className="text-slate-300 focus:text-white focus:bg-white/[0.06]"
            >
              <User className="w-4 h-4 mr-2" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem
              id="nav-settings"
              className="text-slate-300 focus:text-white focus:bg-white/[0.06]"
            >
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-white/[0.06]" />
            <DropdownMenuItem
              id="nav-logout"
              onClick={logout}
              className="text-red-400 focus:text-red-300 focus:bg-red-500/10"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
