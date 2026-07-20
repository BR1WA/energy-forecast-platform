'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertCircle,
  CalendarRange,
  CircleDollarSign,
  Database,
  Gauge,
  PlugZap,
  RefreshCw,
  Settings,
  TimerReset,
  Zap,
} from 'lucide-react';

import AppLayout from '@/components/layout/app-layout';
import { ConsumptionChart } from '@/components/consumption/consumption-chart';
import { PeriodSelector } from '@/components/consumption/period-selector';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button, buttonVariants } from '@/components/ui/button';
import { API_BASE_URL, consumptionApi, getAccessToken } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { ConsumptionPeriodSummary, ConsumptionTimeframe } from '@/types';

type LiveState = 'off' | 'connecting' | 'connected' | 'reconnecting';

interface LiveReading {
  reading_id: number;
  timestamp: string;
  active_power_kw: number;
  source: string;
  quality: string;
}

function ageLabel(seconds: number | null) {
  if (seconds === null) return 'No readings yet';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function localInputValue(date: Date) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function periodLabel(timeframe: ConsumptionTimeframe) {
  return {
    live: 'the last 15 minutes',
    today: 'today',
    '7d': 'the last 7 calendar days',
    month: 'this month',
    year: 'this year',
    all: 'all recorded history',
    custom: 'the custom period',
  }[timeframe];
}

export default function DashboardPage() {
  const [timeframe, setTimeframe] = useState<ConsumptionTimeframe>('today');
  const [summary, setSummary] = useState<ConsumptionPeriodSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveState, setLiveState] = useState<LiveState>('off');
  const [liveReading, setLiveReading] = useState<LiveReading | null>(null);
  const now = useMemo(() => new Date(), []);
  const [customStart, setCustomStart] = useState(localInputValue(new Date(now.getTime() - 7 * 86400_000)));
  const [customEnd, setCustomEnd] = useState(localInputValue(now));
  const cursorRef = useRef(0);

  const loadSummary = useCallback(async (
    selected: ConsumptionTimeframe,
    background = false,
    custom?: { start: string; end: string },
  ) => {
    if (background) setRefreshing(true);
    else {
      setSummary(null);
      setLoading(true);
    }
    try {
      const data = await consumptionApi.getPeriod(selected, custom);
      setSummary(data);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Consumption data is unavailable.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setLiveReading(null);
    if (timeframe === 'custom') {
      setSummary(null);
      setLoading(false);
      return;
    }
    void loadSummary(timeframe);
    if (timeframe !== 'live') return;
    const timer = window.setInterval(() => void loadSummary('live', true), 30_000);
    return () => window.clearInterval(timer);
  }, [loadSummary, timeframe]);

  useEffect(() => {
    if (timeframe !== 'live') {
      setLiveState('off');
      return;
    }

    let socket: WebSocket | null = null;
    let retryTimer: number | null = null;
    let stopped = false;

    const connect = () => {
      const token = getAccessToken();
      if (!token || stopped) return;
      setLiveState(cursorRef.current ? 'reconnecting' : 'connecting');
      const protocol = API_BASE_URL.startsWith('https') ? 'wss' : 'ws';
      const host = API_BASE_URL.replace(/^https?:\/\//, '');
      socket = new WebSocket(`${protocol}://${host}/api/v1/monitoring/live`);
      socket.onopen = () => {
        socket?.send(JSON.stringify({ access_token: token, last_reading_id: cursorRef.current || undefined }));
        setLiveState('connected');
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as { type: 'snapshot' | 'reading'; reading: LiveReading | null };
          const reading = message.reading;
          if (!reading || reading.reading_id <= cursorRef.current) return;
          cursorRef.current = reading.reading_id;
          setLiveReading(reading);
          void loadSummary('live', true);
        } catch {
          socket?.close();
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        setLiveState('reconnecting');
        retryTimer = window.setTimeout(connect, 3000);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      stopped = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [loadSummary, timeframe]);

  const applyCustomRange = () => {
    const start = new Date(customStart);
    const end = new Date(customEnd);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      setError('Choose a custom end time after the start time.');
      return;
    }
    void loadSummary('custom', false, { start: start.toISOString(), end: end.toISOString() });
  };

  const latestPower = timeframe === 'live' && liveReading
    ? liveReading.active_power_kw
    : summary?.points.at(-1)?.average_kw ?? 0;
  const sourceLabel = summary?.sources.map((source) => source.source).join(', ') || 'No source';
  const freshness = summary?.freshness;
  const isEmpty = !loading && summary?.sample_count === 0 && summary.total_kwh === 0;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="mb-1 text-xs font-semibold uppercase text-cyan-400">Single-site electricity monitor</p>
            <h1 className="text-2xl font-semibold text-white">Energy overview</h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-400">
              <span className="inline-flex items-center gap-1.5"><Database className="h-3.5 w-3.5" />{sourceLabel}</span>
              <span className="inline-flex items-center gap-1.5"><Activity className="h-3.5 w-3.5" />{freshness?.status || 'loading'}</span>
              <span>{ageLabel(freshness?.age_seconds ?? null)}</span>
              {timeframe === 'live' && <span>Stream: {liveState}</span>}
            </div>
          </div>
          <div className="flex min-w-0 flex-col items-stretch gap-2 sm:items-end">
            <PeriodSelector disabled={loading} onChange={setTimeframe} value={timeframe} />
            <p className="text-right text-xs text-slate-500">Times shown in {summary?.timezone || 'your site timezone'}</p>
          </div>
        </header>

        {timeframe === 'custom' && (
          <div className="flex flex-col gap-3 border-b border-white/10 pb-5 sm:flex-row sm:items-end">
            <label className="grid gap-1.5 text-xs text-slate-400">
              Start
              <input className="h-9 rounded-md border border-white/10 bg-slate-950 px-3 text-sm text-white" onChange={(event) => setCustomStart(event.target.value)} type="datetime-local" value={customStart} />
            </label>
            <label className="grid gap-1.5 text-xs text-slate-400">
              End
              <input className="h-9 rounded-md border border-white/10 bg-slate-950 px-3 text-sm text-white" onChange={(event) => setCustomEnd(event.target.value)} type="datetime-local" value={customEnd} />
            </label>
            <Button onClick={applyCustomRange}><CalendarRange />Apply range</Button>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" />{error}</span>
            <Button onClick={() => timeframe === 'custom' ? applyCustomRange() : void loadSummary(timeframe)} size="sm" variant="outline">Retry</Button>
          </div>
        )}

        <section className="grid grid-cols-2 gap-3 xl:grid-cols-4" aria-label="Period summary">
          {[
            { label: timeframe === 'live' ? 'Current load' : 'Latest load', value: `${latestPower.toFixed(3)} kW`, icon: Zap },
            { label: 'Energy', value: `${(summary?.total_kwh ?? 0).toFixed(2)} kWh`, icon: Gauge },
            { label: 'Estimated cost', value: `${summary?.currency ?? 'MAD'} ${(summary?.estimated_cost ?? 0).toFixed(2)}`, icon: CircleDollarSign },
            { label: 'Peak load', value: `${(summary?.peak_kw ?? 0).toFixed(3)} kW`, icon: Activity },
          ].map((metric) => (
            <Card className="min-h-28 rounded-lg border-white/10 bg-[#111827]" key={metric.label}>
              <CardContent className="flex h-full flex-col justify-between pt-1">
                <div className="flex items-center justify-between gap-2 text-xs text-slate-400"><span>{metric.label}</span><metric.icon className="h-4 w-4 text-cyan-400" /></div>
                <p className="mt-4 text-xl font-semibold text-white sm:text-2xl">{loading ? '...' : metric.value}</p>
              </CardContent>
            </Card>
          ))}
        </section>

        <Card className="rounded-lg border-white/10 bg-[#111827]">
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle className="text-sm text-white">Measured power</CardTitle>
              <p className="mt-1 text-xs text-slate-400">Average load grouped by {summary?.granularity?.replace('_', ' ') || 'period'} for {periodLabel(timeframe)}.</p>
            </div>
            <Button aria-label="Refresh consumption" disabled={refreshing || loading} onClick={() => timeframe === 'custom' ? applyCustomRange() : void loadSummary(timeframe, true)} size="icon" title="Refresh" variant="ghost">
              <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
            </Button>
          </CardHeader>
          <CardContent>
            {loading && !summary ? (
              <div className="flex h-80 items-center justify-center text-sm text-slate-400"><RefreshCw className="mr-2 h-4 w-4 animate-spin" />Loading measured data</div>
            ) : isEmpty ? (
              <div className="flex h-80 flex-col items-center justify-center gap-3 px-4 text-center">
                <PlugZap className="h-8 w-8 text-slate-500" />
                <div><p className="font-medium text-white">No readings in this period</p><p className="mt-1 text-sm text-slate-400">Connect a meter, import a CSV, or explicitly start the demo simulator.</p></div>
                <div className="flex gap-2"><Link className={buttonVariants({ size: 'sm' })} href="/settings">Set up data</Link><Link className={buttonVariants({ size: 'sm', variant: 'outline' })} href="/simulation">Open simulator</Link></div>
              </div>
            ) : summary ? <ConsumptionChart summary={summary} /> : null}
          </CardContent>
        </Card>

        <section className="grid gap-4 lg:grid-cols-3">
          <div className="border-t border-white/10 pt-4 lg:col-span-2">
            <h2 className="text-sm font-medium text-white">Data quality</h2>
            <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
              <div><p className="text-xs text-slate-500">Coverage</p><p className="mt-1 text-base text-white">{(summary?.coverage_pct ?? 0).toFixed(1)}%</p></div>
              <div><p className="text-xs text-slate-500">Samples</p><p className="mt-1 text-base text-white">{summary?.sample_count.toLocaleString() ?? 0}</p></div>
              <div><p className="text-xs text-slate-500">Quality</p><p className="mt-1 text-base capitalize text-white">{freshness?.quality || 'Unavailable'}</p></div>
              <div><p className="text-xs text-slate-500">Expected interval</p><p className="mt-1 text-base text-white">{freshness?.expected_interval_seconds ? `${freshness.expected_interval_seconds}s` : 'Unknown'}</p></div>
            </div>
            {(summary?.coverage_pct ?? 0) < 95 && (summary?.sample_count ?? 0) > 0 && <p className="mt-4 text-xs text-amber-300">Some intervals are missing or too far apart. Totals exclude unsupported gaps.</p>}
          </div>
          <div className="border-t border-white/10 pt-4">
            <h2 className="text-sm font-medium text-white">Data controls</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link className={buttonVariants({ size: 'sm', variant: 'outline' })} href="/settings"><Settings />Meter settings</Link>
              <Link className={buttonVariants({ size: 'sm', variant: 'outline' })} href="/consumption"><Database />Import history</Link>
              <Link className={buttonVariants({ size: 'sm', variant: 'outline' })} href="/simulation"><TimerReset />Demo simulator</Link>
            </div>
          </div>
        </section>
      </div>
    </AppLayout>
  );
}
