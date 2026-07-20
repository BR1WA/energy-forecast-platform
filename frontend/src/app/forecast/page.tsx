'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  Play,
  RefreshCw,
  TrendingUp,
} from 'lucide-react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { forecastApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import type {
  ForecastReadiness,
  ProductForecast,
  ProductForecastHistoryItem,
} from '@/types';

function formatDate(value: string | null, timezone?: string) {
  if (!value) return 'Not available';
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: timezone,
    }).format(new Date(value));
  } catch {
    return new Date(value).toLocaleString();
  }
}

function methodLabel(method: ProductForecast['method'] | string) {
  if (method === 'global_tft') return 'Global TFT';
  if (method === 'seasonal_naive') return 'Seasonal fallback';
  return 'Unknown';
}

function Fact({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="min-w-0 border-l-2 border-cyan-400/60 pl-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 truncate text-base font-semibold text-white" title={value}>{value}</p>
      {detail ? <p className="mt-1 text-xs text-slate-500">{detail}</p> : null}
    </div>
  );
}

export default function ForecastPage() {
  const [readiness, setReadiness] = useState<ForecastReadiness | null>(null);
  const [forecast, setForecast] = useState<ProductForecast | null>(null);
  const [history, setHistory] = useState<ProductForecastHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const [nextReadiness, latest, nextHistory] = await Promise.all([
        forecastApi.getReadiness(),
        forecastApi.getLatest(),
        forecastApi.getHistory(),
      ]);
      setReadiness(nextReadiness);
      setForecast(latest);
      setHistory(nextHistory);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to load forecast data.';
      setError(message);
      if (quiet) toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runForecast = async () => {
    setRunning(true);
    try {
      const result = await forecastApi.run();
      setForecast(result);
      const [nextReadiness, nextHistory] = await Promise.all([
        forecastApi.getReadiness(),
        forecastApi.getHistory(),
      ]);
      setReadiness(nextReadiness);
      setHistory(nextHistory);
      toast.success(result.method === 'global_tft' ? '24-hour forecast generated.' : 'Seasonal fallback generated.');
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Forecast generation failed.');
    } finally {
      setRunning(false);
    }
  };

  const chartData = useMemo(() => forecast?.points.map((point) => ({
    ...point,
    range: point.p10_kwh !== null && point.p90_kwh !== null
      ? [point.p10_kwh, point.p90_kwh]
      : undefined,
    label: formatDate(point.timestamp, forecast.timezone),
  })) ?? [], [forecast]);

  const summary = useMemo(() => {
    if (!forecast?.points.length) return null;
    const total = forecast.points.reduce((sum, point) => sum + point.p50_kwh, 0);
    const peak = forecast.points.reduce((highest, point) => (
      point.p50_kwh > highest.p50_kwh ? point : highest
    ));
    return { total, peak };
  }, [forecast]);

  const canRun = readiness?.ready_for_tft || readiness?.fallback_available;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
              <BrainCircuit className="h-6 w-6 text-cyan-400" />
              24-hour energy forecast
            </h1>
            <p className="mt-1 text-sm text-slate-400">Primary meter forecast in hourly kWh</p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => void load(true)}
              disabled={loading || running}
              title="Refresh forecast status"
              aria-label="Refresh forecast status"
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </Button>
            <Button onClick={runForecast} disabled={!canRun || running || loading}>
              {running ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {running ? 'Generating' : readiness?.status === 'fallback_ready' ? 'Run fallback' : 'Generate forecast'}
            </Button>
          </div>
        </header>

        {error ? (
          <div className="flex items-center gap-3 border border-red-400/25 bg-red-400/5 px-4 py-3 text-sm text-red-200">
            <AlertTriangle className="h-4 w-4 shrink-0" />{error}
          </div>
        ) : null}

        <section className="border-y border-white/10 bg-white/[0.025] px-4 py-5">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Fact
              label="History coverage"
              value={readiness ? `${readiness.coverage_percent.toFixed(1)}%` : 'Loading'}
              detail="Minimum 95%"
            />
            <Fact
              label="Complete hours"
              value={readiness ? `${readiness.observed_hours} / ${readiness.required_hours}` : 'Loading'}
              detail="Latest 14 days"
            />
            <Fact
              label="Longest gap"
              value={readiness ? `${readiness.maximum_gap_hours}h` : 'Loading'}
              detail="Maximum 3h"
            />
            <Fact
              label="Forecast engine"
              value={readiness?.ready_for_tft ? 'Global TFT ready' : readiness?.fallback_available ? 'Fallback ready' : 'Waiting for data'}
              detail={readiness?.model.version ? `Version ${readiness.model.version}` : undefined}
            />
          </div>
        </section>

        {readiness?.status === 'insufficient_data' ? (
          <Card className="rounded-lg border-amber-400/25 bg-amber-400/[0.04]">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-amber-100">
                <Database className="h-4 w-4" /> More meter history is required
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm text-amber-100/80">
                {readiness.reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
              <Link href="/consumption" className={cn(buttonVariants({ variant: 'outline' }), 'border-amber-300/20 text-amber-100')}>
                Open data workspace
              </Link>
            </CardContent>
          </Card>
        ) : null}

        {forecast && summary ? (
          <>
            {forecast.method === 'seasonal_naive' ? (
              <div className="flex items-start gap-3 border border-amber-400/25 bg-amber-400/[0.04] px-4 py-3 text-sm text-amber-100">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <div><p className="font-medium">Seasonal fallback is active</p><p className="mt-1 text-amber-100/70">{forecast.fallback_reason}</p></div>
              </div>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label="Expected energy" value={`${summary.total.toFixed(2)} kWh`} detail="Median, next 24h" /></CardContent></Card>
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label="Peak hour" value={`${summary.peak.p50_kwh.toFixed(2)} kWh`} detail={formatDate(summary.peak.timestamp, forecast.timezone)} /></CardContent></Card>
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label="Method" value={methodLabel(forecast.method)} detail={`Version ${forecast.model_version}`} /></CardContent></Card>
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label="Input quality" value={`${forecast.coverage_percent.toFixed(1)}%`} detail={forecast.sources.join(', ') || 'Unknown source'} /></CardContent></Card>
            </div>

            <Card className="rounded-lg border-white/10 bg-[#111827]/80">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white"><TrendingUp className="h-4 w-4 text-cyan-400" />Hourly forecast</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[360px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                      <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="timestamp" tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} stroke="#94a3b8" minTickGap={28} />
                      <YAxis stroke="#94a3b8" unit=" kWh" width={72} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 6 }} labelFormatter={(_, payload) => payload?.[0]?.payload?.label ?? ''} formatter={(value, name) => [typeof value === 'number' ? `${value.toFixed(3)} kWh` : value, name === 'p50_kwh' ? 'Median' : '10th-90th percentile']} />
                      <Area type="monotone" dataKey="range" fill="#22d3ee" fillOpacity={0.16} stroke="none" connectNulls={false} />
                      <Line type="monotone" dataKey="p50_kwh" name="Median" stroke="#22d3ee" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-cyan-400" />Median forecast</span>
                  {forecast.method === 'global_tft' ? <span className="flex items-center gap-1.5"><span className="h-3 w-5 bg-cyan-400/20" />10th-90th percentile</span> : null}
                  <span>{forecast.confidence_method}</span>
                </div>
              </CardContent>
            </Card>

            <section className="grid gap-6 border-y border-white/10 py-5 lg:grid-cols-2">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold text-white"><Gauge className="h-4 w-4 text-emerald-400" />Forecast provenance</h2>
                <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
                  <div><dt className="text-slate-500">Input window</dt><dd className="mt-1 text-slate-200">{formatDate(forecast.input_start, forecast.timezone)} to {formatDate(forecast.input_end, forecast.timezone)}</dd></div>
                  <div><dt className="text-slate-500">Forecast window</dt><dd className="mt-1 text-slate-200">{formatDate(forecast.forecast_start, forecast.timezone)} to {formatDate(forecast.forecast_end, forecast.timezone)}</dd></div>
                  <div><dt className="text-slate-500">Observed hours</dt><dd className="mt-1 text-slate-200">{forecast.observed_hours} / 336</dd></div>
                  <div><dt className="text-slate-500">Generated</dt><dd className="mt-1 text-slate-200">{formatDate(forecast.created_at, forecast.timezone)}</dd></div>
                </dl>
              </div>
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold text-white"><CheckCircle2 className="h-4 w-4 text-emerald-400" />Model evidence</h2>
                <p className="mt-4 text-sm leading-6 text-slate-400">Cold-start research evaluation: 0.185 kWh macro MAE across 500 held-out households, 26.5% lower MAE than the weekly seasonal baseline. Client-site accuracy is not yet established.</p>
              </div>
            </section>
          </>
        ) : !loading && readiness?.status !== 'insufficient_data' ? (
          <div className="border-y border-white/10 py-16 text-center">
            <CalendarClock className="mx-auto h-8 w-8 text-slate-600" />
            <p className="mt-3 text-sm text-slate-400">No persisted forecast yet.</p>
          </div>
        ) : null}

        {history.length ? (
          <Card className="rounded-lg border-white/10 bg-[#111827]/80">
            <CardHeader><CardTitle className="flex items-center gap-2 text-white"><Clock3 className="h-4 w-4 text-slate-400" />Recent forecasts</CardTitle></CardHeader>
            <CardContent>
              <div className="divide-y divide-white/10">
                {history.slice(0, 8).map((item) => (
                  <div key={item.id} className="flex flex-col gap-1 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <div><p className="font-medium text-slate-200">{methodLabel(item.method)}</p><p className="text-xs text-slate-500">Forecast from {formatDate(item.forecast_start, forecast?.timezone)}</p></div>
                    <span className="text-xs text-slate-500">Generated {formatDate(item.created_at, forecast?.timezone)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </AppLayout>
  );
}
