'use client';

import { useId, useMemo, useState } from 'react';
import { Activity, BarChart3, Clock3, TriangleAlert } from 'lucide-react';
import {
  Area,
  Bar,
  Brush,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TooltipContentProps } from 'recharts';

import { cn } from '@/lib/utils';
import type { ConsumptionPeriodSummary, ConsumptionTimeframe } from '@/types';

type ChartMode = 'power' | 'energy';
type ChartVariant = 'compact' | 'detailed';

type ChartDatum = {
  timestamp: string;
  timestampMs: number;
  average_kw: number | null;
  min_kw: number | null;
  max_kw: number | null;
  range_kw: readonly [number, number] | null;
  energy_kwh: number | null;
  sample_count: number;
  isGap: boolean;
};

const GRANULARITY_MS: Record<string, number> = {
  minute: 60_000,
  '15_minutes': 15 * 60_000,
  hour: 60 * 60_000,
  day: 24 * 60 * 60_000,
  week: 7 * 24 * 60 * 60_000,
  month: 30 * 24 * 60 * 60_000,
};

function defaultMode(timeframe: ConsumptionPeriodSummary['timeframe']): ChartMode {
  return timeframe === 'year' || timeframe === 'all' ? 'energy' : 'power';
}

function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function formatDateTime(timestamp: number | string, timezone: string) {
  const date = new Date(timestamp);
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: timezone,
    }).format(date);
  } catch {
    return date.toLocaleString();
  }
}

function formatTick(value: number, summary: ConsumptionPeriodSummary) {
  const date = new Date(value);
  const options: Intl.DateTimeFormatOptions = summary.timeframe === 'live' || summary.timeframe === 'today'
    ? { hour: '2-digit', minute: '2-digit' }
    : summary.timeframe === 'year' || summary.granularity === 'month'
      ? { month: 'short', year: '2-digit' }
      : summary.granularity === 'hour'
        ? { weekday: 'short', hour: '2-digit' }
        : summary.granularity === 'minute' || summary.granularity === '15_minutes'
          ? { hour: '2-digit', minute: '2-digit' }
          : { day: '2-digit', month: 'short' };
  try {
    return new Intl.DateTimeFormat(undefined, { ...options, timeZone: summary.timezone }).format(date);
  } catch {
    return date.toLocaleString(undefined, options);
  }
}

function buildChartData(summary: ConsumptionPeriodSummary) {
  const expectedStep = GRANULARITY_MS[summary.granularity] ?? null;
  const points = summary.points
    .map((point): ChartDatum => ({
      ...point,
      timestampMs: new Date(point.timestamp).getTime(),
      range_kw: point.min_kw == null || point.max_kw == null ? null : [point.min_kw, point.max_kw],
      isGap: false,
    }))
    .filter((point) => Number.isFinite(point.timestampMs))
    .sort((a, b) => a.timestampMs - b.timestampMs);

  if (!expectedStep || points.length < 2) return { data: points, gapCount: 0 };

  const data: ChartDatum[] = [];
  let gapCount = 0;
  points.forEach((point, index) => {
    data.push(point);
    const next = points[index + 1];
    if (!next || next.timestampMs - point.timestampMs <= expectedStep * 1.5) return;
    gapCount += 1;
    const gapTimestamp = Math.min(point.timestampMs + expectedStep, next.timestampMs - 1);
    data.push({
      timestamp: new Date(gapTimestamp).toISOString(),
      timestampMs: gapTimestamp,
      average_kw: null,
      min_kw: null,
      max_kw: null,
      range_kw: null,
      energy_kwh: null,
      sample_count: 0,
      isGap: true,
    });
  });
  return { data, gapCount };
}

function ConsumptionTooltip({
  active,
  payload,
  mode,
  timezone,
}: TooltipContentProps & { mode: ChartMode; timezone: string }) {
  const point = payload?.find((entry) => entry.payload)?.payload as ChartDatum | undefined;
  if (!active || !point || point.isGap) return null;

  return (
    <div className="min-w-56 rounded-lg border border-white/15 bg-slate-950/95 p-3 text-xs shadow-2xl backdrop-blur">
      <p className="font-medium text-white">{formatDateTime(point.timestampMs, timezone)}</p>
      <div className="mt-2 space-y-1.5 text-slate-300">
        {mode === 'power' ? (
          <>
            <div className="flex justify-between gap-6"><span>Average power</span><strong className="text-cyan-300">{formatNumber(point.average_kw ?? 0, 3)} kW</strong></div>
            {point.min_kw != null && <div className="flex justify-between gap-6"><span>Minimum</span><span>{formatNumber(point.min_kw, 3)} kW</span></div>}
            {point.max_kw != null && <div className="flex justify-between gap-6"><span>Maximum</span><span>{formatNumber(point.max_kw, 3)} kW</span></div>}
          </>
        ) : (
          <div className="flex justify-between gap-6"><span>Bucket energy</span><strong className="text-indigo-300">{formatNumber(point.energy_kwh ?? 0, 3)} kWh</strong></div>
        )}
        <div className="flex justify-between gap-6 border-t border-white/10 pt-1.5"><span>Samples</span><span>{point.sample_count.toLocaleString()}</span></div>
      </div>
    </div>
  );
}

interface ConsumptionChartProps {
  summary: ConsumptionPeriodSummary;
  variant?: ChartVariant;
}

export function ConsumptionChart({ summary, variant = 'compact' }: ConsumptionChartProps) {
  const [selection, setSelection] = useState<{ timeframe: ConsumptionTimeframe; mode: ChartMode }>(() => ({
    timeframe: summary.timeframe,
    mode: defaultMode(summary.timeframe),
  }));
  const mode = selection.timeframe === summary.timeframe ? selection.mode : defaultMode(summary.timeframe);
  const id = useId().replace(/:/g, '');
  const { data, gapCount } = useMemo(() => buildChartData(summary), [summary]);
  const detailed = variant === 'detailed';
  const unit = mode === 'power' ? 'kW' : 'kWh';
  const metricLabel = mode === 'power' ? 'Average active power' : `Energy per ${summary.granularity.replace('_', ' ')} bucket`;
  const peakTimestamp = summary.peak_at ? new Date(summary.peak_at).getTime() : null;
  const hasRange = data.some((point) => point.range_kw != null && point.min_kw !== point.max_kw);
  const powerMaximum = Math.max(summary.peak_kw, ...data.map((point) => point.max_kw ?? point.average_kw ?? 0));
  const energyMaximum = Math.max(...data.map((point) => point.energy_kwh ?? 0));
  const yMaximum = Math.max(1, (mode === 'power' ? powerMaximum : energyMaximum) * 1.16);
  const coverageTone = summary.coverage_pct >= 90
    ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200'
    : 'border-amber-400/25 bg-amber-400/10 text-amber-200';

  const candidateTicks = data.length <= 31 ? data.map((point) => point.timestampMs) : undefined;

  return (
    <figure aria-label={`${metricLabel} chart for ${summary.site_name}`} className="min-w-0">
      {detailed && (
        <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2.5 py-1 text-cyan-100">
              <Activity className="h-3.5 w-3.5" />{metricLabel} ({unit})
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-slate-300">
              <Clock3 className="h-3.5 w-3.5" />{summary.timezone} · {summary.granularity.replace('_', ' ')} buckets
            </span>
            <span className={cn('rounded-full border px-2.5 py-1', coverageTone)}>{summary.coverage_pct.toFixed(1)}% coverage</span>
          </div>
          <div aria-label="Chart metric" className="inline-flex w-fit rounded-lg border border-white/10 bg-black/20 p-1" role="group">
            <button aria-pressed={mode === 'power'} className={cn('inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors', mode === 'power' ? 'bg-cyan-400 text-slate-950' : 'text-slate-400 hover:bg-white/5 hover:text-white')} onClick={() => setSelection({ timeframe: summary.timeframe, mode: 'power' })} type="button"><Activity className="h-3.5 w-3.5" />Power</button>
            <button aria-pressed={mode === 'energy'} className={cn('inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors', mode === 'energy' ? 'bg-indigo-400 text-slate-950' : 'text-slate-400 hover:bg-white/5 hover:text-white')} onClick={() => setSelection({ timeframe: summary.timeframe, mode: 'energy' })} type="button"><BarChart3 className="h-3.5 w-3.5" />Energy</button>
          </div>
        </div>
      )}

      {detailed && gapCount > 0 && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.07] px-3 py-2 text-xs leading-5 text-amber-100">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{gapCount} measurement gap{gapCount === 1 ? '' : 's'} shown as a break in the curve; values are not interpolated across missing intervals.</span>
        </div>
      )}

      <div className={cn('w-full min-w-0', detailed ? 'h-[380px]' : 'h-72')}>
        <ResponsiveContainer height="100%" initialDimension={{ width: 320, height: detailed ? 380 : 288 }} minWidth={0} width="100%">
          <ComposedChart accessibilityLayer data={data} margin={{ bottom: detailed && data.length > 36 ? 8 : 2, left: 0, right: 18, top: 20 }}>
            <defs>
              <linearGradient id={`${id}-range`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.24} />
                <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.04} />
              </linearGradient>
              <linearGradient id={`${id}-energy`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#818cf8" stopOpacity={0.95} />
                <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.45} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" strokeDasharray="3 5" vertical={false} />
            <XAxis
              dataKey="timestampMs"
              domain={['dataMin', 'dataMax']}
              fontSize={11}
              minTickGap={20}
              scale="time"
              stroke="#64748b"
              tickFormatter={(value) => formatTick(Number(value), summary)}
              tickLine={false}
              ticks={candidateTicks}
              type="number"
            />
            <YAxis
              allowDecimals
              domain={[0, yMaximum]}
              fontSize={11}
              stroke="#64748b"
              tickFormatter={(value) => formatNumber(Number(value), Number(value) < 10 ? 2 : 0)}
              tickLine={false}
              width={48}
            />
            <Tooltip content={(props) => <ConsumptionTooltip {...props} mode={mode} timezone={summary.timezone} />} cursor={{ stroke: 'rgba(103,232,249,0.4)', strokeDasharray: '4 4' }} />

            {mode === 'power' ? (
              <>
                {hasRange && <Area activeDot={false} connectNulls={false} dataKey="range_kw" fill={`url(#${id}-range)`} isAnimationActive={false} legendType="none" stroke="none" type="linear" />}
                <Line activeDot={{ fill: '#0f172a', r: 4, stroke: '#67e8f9', strokeWidth: 2 }} connectNulls={false} dataKey="average_kw" dot={false} isAnimationActive={false} name="Average power" stroke="#22d3ee" strokeWidth={2.4} type="linear" />
                {summary.average_kw > 0 && <ReferenceLine ifOverflow="extendDomain" label={{ fill: '#94a3b8', fontSize: 10, position: 'insideTopRight', value: `Average ${formatNumber(summary.average_kw, 2)} kW` }} stroke="#94a3b8" strokeDasharray="5 5" y={summary.average_kw} />}
                {peakTimestamp != null && Number.isFinite(peakTimestamp) && summary.peak_kw > 0 && <ReferenceDot fill="#fbbf24" ifOverflow="extendDomain" label={{ fill: '#fcd34d', fontSize: 10, position: 'top', value: `Peak ${formatNumber(summary.peak_kw, 2)} kW` }} r={4.5} stroke="#111827" strokeWidth={2} x={peakTimestamp} y={summary.peak_kw} />}
              </>
            ) : (
              <Bar dataKey="energy_kwh" fill={`url(#${id}-energy)`} isAnimationActive={false} maxBarSize={detailed ? 32 : 20} name="Energy" radius={[4, 4, 0, 0]} />
            )}

            {detailed && data.length > 36 && (
              <Brush dataKey="timestampMs" fill="#0f172a" height={24} stroke="#334155" tickFormatter={(value) => formatTick(Number(value), summary)} travellerWidth={8} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <div className="flex flex-wrap items-center gap-3">
          {mode === 'power' ? <><span><i className="mr-1.5 inline-block h-0.5 w-4 bg-cyan-400 align-middle" />Average power</span>{hasRange && <span><i className="mr-1.5 inline-block h-2.5 w-4 rounded-sm bg-cyan-400/20 align-middle" />Observed min-max</span>}<span><i className="mr-1.5 inline-block h-0.5 w-4 border-t border-dashed border-slate-400 align-middle" />Period average</span></> : <span><i className="mr-1.5 inline-block h-2.5 w-4 rounded-sm bg-indigo-400/70 align-middle" />Energy per bucket</span>}
        </div>
        {detailed && <span>{summary.sample_count.toLocaleString()} readings · {data.filter((point) => !point.isGap).length.toLocaleString()} displayed buckets</span>}
      </div>
      <figcaption className="sr-only">{metricLabel} for {summary.site_name}, displayed in the {summary.timezone} timezone with {summary.coverage_pct.toFixed(1)} percent data coverage.</figcaption>
    </figure>
  );
}
