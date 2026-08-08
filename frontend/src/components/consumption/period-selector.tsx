'use client';

import type { ConsumptionTimeframe } from '@/types';
import { cn } from '@/lib/utils';

const PERIODS: Array<{ value: ConsumptionTimeframe; label: string }> = [
  { value: 'live', label: 'Live' },
  { value: 'today', label: 'Today' },
  { value: '7d', label: 'Week' },
  { value: 'month', label: 'Month' },
  { value: 'year', label: 'Year' },
  { value: 'all', label: 'All' },
  { value: 'custom', label: 'Custom' },
];

interface PeriodSelectorProps {
  value: ConsumptionTimeframe;
  onChange: (value: ConsumptionTimeframe) => void;
  disabled?: boolean;
}

export function PeriodSelector({ value, onChange, disabled }: PeriodSelectorProps) {
  return (
    <div
      aria-label="Consumption period"
      className="flex max-w-full gap-1 overflow-x-auto rounded-lg border border-white/10 bg-black/20 p-1"
      role="tablist"
    >
      {PERIODS.map((period) => (
        <button
          aria-selected={value === period.value}
          className={cn(
            'h-8 shrink-0 rounded-md px-3 text-xs font-medium transition-colors',
            value === period.value
              ? 'bg-cyan-500 text-slate-950'
              : 'text-slate-400 hover:bg-white/5 hover:text-white',
          )}
          disabled={disabled}
          key={period.value}
          onClick={() => onChange(period.value)}
          role="tab"
          type="button"
        >
          {period.label}
        </button>
      ))}
    </div>
  );
}
