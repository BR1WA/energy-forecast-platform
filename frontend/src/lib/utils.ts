import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function parseDate(dateStr: string | null | undefined): Date {
  if (!dateStr) return new Date();
  
  // If the date string doesn't specify a timezone, treat it as UTC
  let normalized = dateStr;
  if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !/-\d{2}:\d{2}$/.test(dateStr)) {
    // If there is a space instead of T, replace it for standard format
    normalized = dateStr.replace(' ', 'T') + 'Z';
  }
  return new Date(normalized);
}

export function formatTimeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const date = parseDate(dateStr);
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

