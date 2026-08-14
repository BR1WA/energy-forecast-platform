'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  Gauge,
  Play,
  RefreshCw,
  Sparkles,
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
import { analyticsApi, forecastApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import type {
  ForecastCapability,
  ForecastHorizon,
  ForecastReadiness,
  ProductForecast,
  ProductForecastHistoryItem,
  ProductForecastPoint,
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

function formatDay(value: string, timezone?: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: timezone,
    }).format(new Date(value));
  } catch {
    return new Date(value).toLocaleDateString();
  }
}

function methodLabel(method: ProductForecast['method'] | string) {
  if (method === 'global_tft') return 'Global TFT';
  if (method === 'chronos2_lora') return 'Chronos-2 LoRA';
  if (method === 'seasonal_naive') return 'Seasonal fallback';
  return 'Unknown';
}

function horizonLabel(horizon: ForecastHorizon | number) {
  if (horizon === 720) return '30-day daily';
  if (horizon === 168) return '7-day / 168-hour';
  return '24-hour';
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

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

type ChartPoint = {
  timestamp: string;
  p50_kwh: number;
  range?: [number, number];
  label: string;
};

function dailyChartData(points: ProductForecastPoint[], timezone: string): ChartPoint[] {
  const grouped = new Map<string, ProductForecastPoint[]>();
  for (const point of points) {
    const key = new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: timezone,
    }).format(new Date(point.timestamp));
    grouped.set(key, [...(grouped.get(key) ?? []), point]);
  }
  return Array.from(grouped.values()).map((day) => {
    const hasInterval = day.every((point) => point.p10_kwh !== null && point.p90_kwh !== null);
    const timestamp = day[0].timestamp;
    return {
      timestamp,
      p50_kwh: day.reduce((sum, point) => sum + point.p50_kwh, 0),
      range: hasInterval
        ? [
            day.reduce((sum, point) => sum + (point.p10_kwh ?? 0), 0),
            day.reduce((sum, point) => sum + (point.p90_kwh ?? 0), 0),
          ]
        : undefined,
      label: formatDay(timestamp, timezone),
    };
  });
}

function ForecastContent() {
  const searchParams = useSearchParams();
  const requestedHorizon = searchParams.get('horizon');
  const horizon: ForecastHorizon = requestedHorizon === '720'
    ? 720
    : requestedHorizon === '168'
      ? 168
      : 24;
  const [capabilities, setCapabilities] = useState<ForecastCapability[]>([]);
  const [readiness, setReadiness] = useState<ForecastReadiness | null>(null);
  const [forecast, setForecast] = useState<ProductForecast | null>(null);
  const [history, setHistory] = useState<ProductForecastHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [preparingDemo, setPreparingDemo] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const capabilityResult = await forecastApi.getCapabilities();
      setCapabilities(capabilityResult.capabilities);
      if (!capabilityResult.capabilities.some((capability) => capability.horizon_hours === horizon)) {
        setReadiness(null);
        setForecast(null);
        setHistory([]);
        throw new Error(
          `The ${horizonLabel(horizon)} forecast is unavailable in this runtime. `
          + 'Ask the operator to enable and warm its packaged model.',
        );
      }
      const [nextReadiness, latest, nextHistory] = await Promise.all([
        forecastApi.getReadiness(horizon),
        forecastApi.getLatest(horizon),
        forecastApi.getHistory(horizon),
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
  }, [horizon]);

  useEffect(() => {
    void load();
  }, [load]);

  const runForecast = async () => {
    setRunning(true);
    try {
      const result = await forecastApi.run(horizon);
      setForecast(result);
      const [nextReadiness, nextHistory] = await Promise.all([
        forecastApi.getReadiness(horizon),
        forecastApi.getHistory(horizon),
      ]);
      setReadiness(nextReadiness);
      setHistory(nextHistory);
      toast.success(
        result.method === 'seasonal_naive'
          ? `${horizonLabel(horizon)} seasonal fallback generated.`
          : `${horizonLabel(horizon)} forecast generated.`,
      );
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Forecast generation failed.');
    } finally {
      setRunning(false);
    }
  };

  const prepareDemoHistory = async () => {
    setPreparingDemo(true);
    try {
      const result = await forecastApi.prepareDemoHistory();
      await load(true);
      if (result.status === 'ready') {
        toast.success(`Demo history ready: ${result.coverage_percent.toFixed(1)}% coverage.`);
      } else {
        toast.warning(result.message);
      }
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Demo history preparation failed.');
    } finally {
      setPreparingDemo(false);
    }
  };

  const exportForecast = async () => {
    if (!forecast) return;
    setExporting(true);
    try {
      const suffix = forecast.resolution === 'daily' ? '30d' : `${forecast.horizon_hours}h`;
      saveBlob(await analyticsApi.downloadReportPDF(forecast.id), `energy-forecast-${suffix}-${forecast.id}.pdf`);
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Forecast PDF export failed.');
    } finally {
      setExporting(false);
    }
  };

  const chartData = useMemo<ChartPoint[]>(() => {
    if (!forecast) return [];
    if (forecast.horizon_hours === 168) return dailyChartData(forecast.points, forecast.timezone);
    return forecast.points.map((point) => ({
      timestamp: point.timestamp,
      p50_kwh: point.p50_kwh,
      range: point.p10_kwh !== null && point.p90_kwh !== null
        ? [point.p10_kwh, point.p90_kwh]
        : undefined,
      label: forecast.resolution === 'daily'
        ? formatDay(point.timestamp, forecast.timezone)
        : formatDate(point.timestamp, forecast.timezone),
    }));
  }, [forecast]);

  const summary = useMemo(() => {
    if (!forecast?.points.length) return null;
    const total = forecast.points.reduce((sum, point) => sum + point.p50_kwh, 0);
    const peak = forecast.points.reduce((highest, point) => (
      point.p50_kwh > highest.p50_kwh ? point : highest
    ));
    const minimum = forecast.points.reduce((lowest, point) => (
      point.p50_kwh < lowest.p50_kwh ? point : lowest
    ));
    return { total, average: total / forecast.points.length, peak, minimum };
  }, [forecast]);

  const canRun = readiness?.ready_for_model || readiness?.fallback_available;
  const isWeek = horizon === 168;
  const isMonth = horizon === 720;
  const chartIsDaily = forecast?.resolution === 'daily' || forecast?.horizon_hours === 168;
  const directDailyTargets = forecast?.resolution === 'daily';

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
              <BrainCircuit className="h-6 w-6 text-cyan-400" />
              {isMonth
                ? 'Next 30 days · daily energy forecast'
                : isWeek
                  ? 'Next 7 days · 168-hour energy forecast'
                  : 'Next 24 hours energy forecast'}
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Primary meter forecast in {isMonth ? 'daily' : 'hourly'} kWh
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {capabilities.length > 1 ? (
              <div className="flex rounded-md border border-white/10 bg-slate-950/50 p-1" aria-label="Forecast horizon">
                {capabilities.map((capability) => (
                  <Link
                    key={capability.horizon_hours}
                    aria-current={horizon === capability.horizon_hours ? 'page' : undefined}
                    aria-disabled={loading || running}
                    className={cn(
                      buttonVariants({
                        size: 'sm',
                        variant: horizon === capability.horizon_hours ? 'default' : 'ghost',
                      }),
                      (loading || running) && 'pointer-events-none opacity-50',
                    )}
                    href={`/forecast?horizon=${capability.horizon_hours}`}
                    replace
                    scroll={false}
                    title={capability.description}
                  >
                    {capability.label}
                  </Link>
                ))}
              </div>
            ) : null}
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
              <Button variant="outline" onClick={() => void exportForecast()} disabled={!forecast || exporting || loading || running}>
                <Download className="h-4 w-4" />{exporting ? 'Exporting' : 'Forecast PDF'}
              </Button>
            </div>
          </div>
        </header>

        {error ? (
          <div className="flex items-center gap-3 border border-red-400/25 bg-red-400/5 px-4 py-3 text-sm text-red-200">
            <AlertTriangle className="h-4 w-4 shrink-0" />{error}
          </div>
        ) : null}

        <section className="border-y border-white/10 bg-white/[0.025] px-4 py-5">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Fact label="History coverage" value={readiness ? `${readiness.coverage_percent.toFixed(1)}%` : 'Loading'} detail="Minimum 95%" />
            <Fact
              label={isMonth ? 'Complete days' : 'Complete hours'}
              value={readiness
                ? isMonth
                  ? `${readiness.observed_days} / ${readiness.required_days ?? 270}`
                  : `${readiness.observed_hours} / ${readiness.required_hours}`
                : 'Loading'}
              detail={isMonth ? 'Up to 365 rolling daily blocks' : 'Latest 14 days'}
            />
            <Fact
              label="Longest gap"
              value={readiness
                ? isMonth
                  ? `${readiness.maximum_gap_days}d`
                  : `${readiness.maximum_gap_hours}h`
                : 'Loading'}
              detail={isMonth ? 'Maximum 3 internal days' : 'Maximum 3h'}
            />
            <Fact
              label="Forecast engine"
              value={readiness?.ready_for_model
                ? isMonth ? 'Chronos-2 LoRA ready' : 'Global TFT ready'
                : readiness?.fallback_available ? 'Fallback ready' : 'Waiting for data'}
              detail={readiness?.model.version ? `Version ${readiness.model.version}` : undefined}
            />
          </div>
        </section>

        {readiness?.status === 'insufficient_data' ? (
          <Card className="rounded-lg border-amber-400/25 bg-amber-400/[0.04]">
            <CardHeader><CardTitle className="flex items-center gap-2 text-amber-100"><Database className="h-4 w-4" /> More meter history is required</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm text-amber-100/80">
                {readiness.reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
              <div className="flex flex-wrap gap-3">
                {!isMonth ? (
                  <Button
                    className="bg-amber-300 text-slate-950 hover:bg-amber-200"
                    onClick={() => void prepareDemoHistory()}
                    disabled={preparingDemo || loading || running}
                  >
                    {preparingDemo ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    {preparingDemo ? 'Preparing history' : 'Prepare demo history'}
                  </Button>
                ) : null}
                <Link href="/usage" className={cn(buttonVariants({ variant: 'outline' }), 'border-amber-300/20 text-amber-100')}>Open Usage</Link>
                <a download href="/samples/forecast-ready" className={cn(buttonVariants({ variant: 'outline' }), 'border-amber-300/20 text-amber-100')}><Download className="h-4 w-4" />Download forecast-ready CSV</a>
              </div>
              <p className="text-xs leading-5 text-amber-100/60">
                {isMonth
                  ? 'The production monthly model requires at least 270 complete rolling daily blocks. Short synthetic demo history is deliberately not expanded to satisfy this gate.'
                  : 'For demos and tests, one-click preparation adds clearly labelled synthetic hourly readings to the current primary meter. It preserves existing readings and is safe to run again. The CSV remains available for testing the manual import journey.'}
              </p>
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
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label="Expected energy" value={`${summary.total.toFixed(2)} kWh`} detail={`Median total, ${horizonLabel(forecast.horizon_hours)}`} /></CardContent></Card>
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label={directDailyTargets ? 'Average day' : 'Average hour'} value={`${summary.average.toFixed(2)} kWh`} detail={`${forecast.points.length} ${forecast.resolution} targets`} /></CardContent></Card>
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label={directDailyTargets ? 'Peak day' : 'Peak hour'} value={`${summary.peak.p50_kwh.toFixed(2)} kWh`} detail={directDailyTargets ? formatDay(summary.peak.timestamp, forecast.timezone) : formatDate(summary.peak.timestamp, forecast.timezone)} /></CardContent></Card>
              <Card className="rounded-lg border-white/10 bg-[#111827]/80"><CardContent className="pt-1"><Fact label={directDailyTargets ? 'Minimum day' : 'Minimum hour'} value={`${summary.minimum.p50_kwh.toFixed(2)} kWh`} detail={directDailyTargets ? formatDay(summary.minimum.timestamp, forecast.timezone) : formatDate(summary.minimum.timestamp, forecast.timezone)} /></CardContent></Card>
            </div>

            <Card className="rounded-lg border-white/10 bg-[#111827]/80">
              <CardHeader><CardTitle className="flex items-center gap-2 text-white"><TrendingUp className="h-4 w-4 text-cyan-400" />{directDailyTargets ? '30 daily energy targets' : chartIsDaily ? 'Daily week-ahead totals' : 'Hourly forecast'}</CardTitle></CardHeader>
              <CardContent>
                <div className="h-[360px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                      <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="timestamp" tickFormatter={(value) => chartIsDaily ? formatDay(value, forecast.timezone) : new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} stroke="#94a3b8" minTickGap={28} />
                      <YAxis stroke="#94a3b8" unit=" kWh" width={72} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 6 }} labelFormatter={(_, payload) => payload?.[0]?.payload?.label ?? ''} formatter={(value, name) => [typeof value === 'number' ? `${value.toFixed(3)} kWh` : value, name === 'p50_kwh' ? (chartIsDaily ? 'Daily median total' : 'Median') : '10th-90th percentile']} />
                      <Area type="monotone" dataKey="range" fill="#22d3ee" fillOpacity={0.16} stroke="none" connectNulls={false} />
                      <Line type="monotone" dataKey="p50_kwh" name="Median" stroke="#22d3ee" strokeWidth={2} dot={chartIsDaily} activeDot={{ r: 4 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-cyan-400" />{chartIsDaily ? 'Daily median total' : 'Median forecast'}</span>
                  {forecast.method !== 'seasonal_naive' ? <span className="flex items-center gap-1.5"><span className="h-3 w-5 bg-cyan-400/20" />10th-90th percentile</span> : null}
                  <span>{chartIsDaily && !directDailyTargets ? 'Chart groups all 168 hourly targets into local calendar days. ' : ''}{forecast.confidence_method}</span>
                </div>
              </CardContent>
            </Card>

            <section className="grid gap-6 border-y border-white/10 py-5 lg:grid-cols-2">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold text-white"><Gauge className="h-4 w-4 text-emerald-400" />Forecast provenance</h2>
                <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
                  <div><dt className="text-slate-500">Input window</dt><dd className="mt-1 text-slate-200">{formatDate(forecast.input_start, forecast.timezone)} to {formatDate(forecast.input_end, forecast.timezone)}</dd></div>
                  <div><dt className="text-slate-500">Forecast window</dt><dd className="mt-1 text-slate-200">{formatDate(forecast.forecast_start, forecast.timezone)} to {formatDate(forecast.forecast_end, forecast.timezone)}</dd></div>
                  <div><dt className="text-slate-500">Observed history</dt><dd className="mt-1 text-slate-200">{directDailyTargets ? `${readiness?.observed_days ?? 0} complete days` : `${forecast.observed_hours} / 336 hours`}</dd></div>
                  <div><dt className="text-slate-500">Targets</dt><dd className="mt-1 text-slate-200">{forecast.target_count} {forecast.resolution} values</dd></div>
                  <div><dt className="text-slate-500">Generated</dt><dd className="mt-1 text-slate-200">{formatDate(forecast.created_at, forecast.timezone)}</dd></div>
                  <div><dt className="text-slate-500">Artifact</dt><dd className="mt-1 break-all font-mono text-xs text-slate-300">{forecast.artifact_fingerprint || 'Seasonal fallback; no model artifact'}</dd></div>
                </dl>
              </div>
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold text-white"><CheckCircle2 className="h-4 w-4 text-emerald-400" />Model evidence</h2>
                <p className="mt-4 text-sm leading-6 text-slate-400">
                  {isMonth
                    ? 'Fresh Tetouan transfer gate: macro MASE 1.095, 49.8% better than the strongest declared seasonal comparator, daily macro R² 0.450, and 88.1% central-80% coverage. A separate southern-Morocco diagnostic did not beat its seasonal baseline.'
                    : isWeek
                      ? 'Cold-start research evaluation: 0.197 kWh macro MAE across 499 held-out households, 20.8% lower MAE than the weekly seasonal baseline; 98.4% of households beat that baseline.'
                      : 'Cold-start research evaluation: 0.185 kWh macro MAE across 500 held-out households, 26.5% lower MAE than the weekly seasonal baseline.'}
                  {' '}Client-site accuracy is not yet established.
                </p>
              </div>
            </section>
          </>
        ) : !loading && readiness?.status !== 'insufficient_data' ? (
          <div className="border-y border-white/10 py-16 text-center">
            <CalendarClock className="mx-auto h-8 w-8 text-slate-600" />
            <p className="mt-3 text-sm text-slate-400">No persisted {horizonLabel(horizon)} forecast yet.</p>
          </div>
        ) : null}

        {history.length ? (
          <Card className="rounded-lg border-white/10 bg-[#111827]/80">
            <CardHeader><CardTitle className="flex items-center gap-2 text-white"><Clock3 className="h-4 w-4 text-slate-400" />Recent {horizonLabel(horizon)} forecasts</CardTitle></CardHeader>
            <CardContent>
              <div className="divide-y divide-white/10">
                {history.slice(0, 8).map((item) => (
                  <div key={item.id} className="flex flex-col gap-1 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <div><p className="font-medium text-slate-200">{methodLabel(item.method)} · {horizonLabel(item.horizon_hours)}</p><p className="text-xs text-slate-500">Forecast from {formatDate(item.forecast_start, forecast?.timezone)}</p></div>
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

export default function ForecastPage() {
  return (
    <Suspense fallback={<AppLayout><div className="mx-auto max-w-7xl py-16 text-center text-sm text-slate-400">Loading forecast horizon…</div></AppLayout>}>
      <ForecastContent />
    </Suspense>
  );
}
