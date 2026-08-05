'use client';

import { useCallback, useEffect, useState } from 'react';
import { CalendarRange, Download, FileCheck2, RefreshCw, Rows3, Upload } from 'lucide-react';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { ConsumptionChart } from '@/components/consumption/consumption-chart';
import { PeriodSelector } from '@/components/consumption/period-selector';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { consumptionApi, ingestionApi } from '@/lib/api';
import type { ConsumptionPeriodSummary, ConsumptionReading, ConsumptionTimeframe, PrimaryMeter } from '@/types';

function localInputValue(date: Date) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export default function UsagePage() {
  const [timeframe, setTimeframe] = useState<ConsumptionTimeframe>('month');
  const [summary, setSummary] = useState<ConsumptionPeriodSummary | null>(null);
  const [meter, setMeter] = useState<PrimaryMeter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ mapped_columns: string[]; valid_rows: number; rejected_rows: number; errors: Array<{ row: number; message: string }> } | null>(null);
  const [importing, setImporting] = useState(false);
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [readings, setReadings] = useState<ConsumptionReading[]>([]);
  const [readingCursor, setReadingCursor] = useState<string | null>(null);
  const [readingsLoading, setReadingsLoading] = useState(false);

  const loadSummary = useCallback(async (selected: ConsumptionTimeframe, custom?: { start: string; end: string }) => {
    setLoading(true);
    setSummary(null);
    setError(null);
    try {
      setSummary(await consumptionApi.getPeriod(selected, custom));
    } catch (requestError) {
      setSummary(null);
      setError(requestError instanceof Error ? requestError.message : 'Unable to load consumption history.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadReadings = useCallback(async (append = false) => {
    if (!summary) return;
    setReadingsLoading(true);
    try {
      const page = await consumptionApi.getReadings(timeframe, {
        start: timeframe === 'custom' ? summary.period_start : undefined,
        end: timeframe === 'custom' ? summary.period_end : undefined,
        cursor: append ? readingCursor || undefined : undefined,
        limit: 50,
      });
      setReadings((current) => append ? [...current, ...page.items] : page.items);
      setReadingCursor(page.next_cursor);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : 'Unable to load raw readings.');
    } finally {
      setReadingsLoading(false);
    }
  }, [readingCursor, summary, timeframe]);

  useEffect(() => {
    ingestionApi.getMeters().then((meters) => setMeter(meters[0] ?? null)).catch(() => setMeter(null));
    const now = new Date();
    setCustomStart(localInputValue(new Date(now.getTime() - 7 * 86400_000)));
    setCustomEnd(localInputValue(now));
  }, []);

  useEffect(() => {
    if (timeframe === 'custom') {
      setSummary(null);
      setLoading(false);
      return;
    }
    void loadSummary(timeframe);
  }, [loadSummary, timeframe]);

  useEffect(() => {
    setReadings([]);
    setReadingCursor(null);
    if (summary) void loadReadings(false);
    // A new period summary resets the keyset cursor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary?.period_start, summary?.period_end]);

  const applyCustomRange = () => {
    const start = new Date(customStart);
    const end = new Date(customEnd);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      setError('Choose a custom end time after the start time.');
      return;
    }
    void loadSummary('custom', { start: start.toISOString(), end: end.toISOString() });
  };

  const previewCsv = async (file: File) => {
    if (!meter) {
      toast.error('Your primary meter is unavailable.');
      return;
    }
    setCsvFile(file);
    setPreview(null);
    try {
      const result = await ingestionApi.previewCsv(meter.id, file);
      setPreview(result);
      if (result.valid_rows === 0) toast.error('This CSV has no valid readings.');
    } catch (requestError) {
      setCsvFile(null);
      toast.error(requestError instanceof Error ? requestError.message : 'Unable to preview this CSV.');
    }
  };

  const importCsv = async () => {
    if (!meter || !csvFile || !preview?.valid_rows) return;
    setImporting(true);
    try {
      const result = await ingestionApi.importCsv(meter.id, csvFile);
      toast.success(`Imported ${result.accepted_rows} reading(s); ${result.duplicate_rows} duplicate(s) skipped.`);
      if (result.rejected_rows) toast.warning(`${result.rejected_rows} row(s) were rejected.`);
      setCsvFile(null);
      setPreview(null);
      await loadSummary(timeframe === 'custom' ? 'all' : timeframe);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : 'CSV import failed.');
    } finally {
      setImporting(false);
    }
  };

  const exportCurrentMonth = async () => {
    try {
      const blob = await consumptionApi.exportCsv();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'energy-current-month.csv';
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : 'Export failed.');
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div><p className="mb-1 text-xs font-semibold uppercase text-cyan-400">Primary meter history</p><h1 className="text-2xl font-semibold text-white">Usage</h1><p className="mt-1 text-sm text-slate-400">Understand measured energy, estimated tariff cost, data coverage, and imported history.</p></div>
          <div className="flex min-w-0 flex-col gap-2 sm:items-end"><PeriodSelector disabled={loading} onChange={setTimeframe} value={timeframe} /><Button onClick={exportCurrentMonth} size="sm" variant="outline"><Download />Export current month</Button></div>
        </header>

        {timeframe === 'custom' && <div className="flex flex-col gap-3 border-b border-white/10 pb-5 sm:flex-row sm:items-end"><label className="grid gap-1.5 text-xs text-slate-400">Start<input className="h-9 rounded-md border border-white/10 bg-slate-950 px-3 text-sm text-white" onChange={(event) => setCustomStart(event.target.value)} type="datetime-local" value={customStart} /></label><label className="grid gap-1.5 text-xs text-slate-400">End<input className="h-9 rounded-md border border-white/10 bg-slate-950 px-3 text-sm text-white" onChange={(event) => setCustomEnd(event.target.value)} type="datetime-local" value={customEnd} /></label><Button onClick={applyCustomRange}><CalendarRange />Apply range</Button></div>}

        {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}

        <p className="text-xs leading-5 text-slate-500">Costs are estimates calculated from the peak and off-peak tariff rates configured in Settings; they may not match a utility bill with taxes, fixed fees, or tiered pricing.</p>

        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[['Energy', `${(summary?.total_kwh ?? 0).toFixed(2)} kWh`], ['Estimated cost', `${summary?.currency ?? 'MAD'} ${(summary?.estimated_cost ?? 0).toFixed(2)}`], ['Peak load', `${(summary?.peak_kw ?? 0).toFixed(3)} kW`], ['Coverage', `${(summary?.coverage_pct ?? 0).toFixed(1)}%`]].map(([label, value]) => <div className="min-h-24 rounded-lg border border-white/10 bg-[#111827] p-4" key={label}><p className="text-xs text-slate-500">{label}</p><p className="mt-4 text-xl font-semibold text-white">{loading ? '...' : value}</p></div>)}
        </section>

        <Card className="rounded-lg border-white/10 bg-[#111827]">
          <CardHeader className="flex-row items-start justify-between"><div><CardTitle className="text-sm">Consumption curve</CardTitle><p className="mt-1 text-xs text-slate-400">{summary ? `${summary.sample_count.toLocaleString()} samples from ${summary.sources.map((source) => source.source).join(', ') || 'no source'}, grouped by ${summary.granularity.replace('_', ' ')}.` : 'Choose a period to inspect its readings.'}</p></div><Button aria-label="Refresh history" disabled={loading} onClick={() => timeframe === 'custom' ? applyCustomRange() : void loadSummary(timeframe)} size="icon" title="Refresh" variant="ghost"><RefreshCw className={loading ? 'animate-spin' : ''} /></Button></CardHeader>
          <CardContent>{summary?.points.length ? <ConsumptionChart summary={summary} /> : <div className="flex h-80 items-center justify-center text-sm text-slate-400">No readings are available in this period.</div>}</CardContent>
        </Card>

        <Card className="rounded-lg border-white/10 bg-[#111827]">
          <CardHeader className="flex-row items-start justify-between gap-3"><div><CardTitle className="flex items-center gap-2 text-sm"><Rows3 className="h-4 w-4 text-indigo-400" />Raw primary-meter readings</CardTitle><p className="mt-1 text-xs text-slate-400">Newest first, bounded to the selected timeframe.</p></div><Button aria-label="Refresh raw readings" title="Refresh raw readings" size="icon" variant="ghost" disabled={readingsLoading || !summary} onClick={() => void loadReadings(false)}><RefreshCw className={readingsLoading ? 'animate-spin' : ''} /></Button></CardHeader>
          <CardContent>
            {readings.length ? <><div className="overflow-x-auto border border-white/10"><div className="grid min-w-[720px] grid-cols-[210px_110px_100px_100px_100px_1fr] bg-white/[0.03] px-3 py-2 text-xs text-slate-500"><span>Timestamp</span><span>Active power</span><span>Voltage</span><span>Current</span><span>Source</span><span>Quality</span></div>{readings.map((reading) => <div key={reading.id} className="grid min-w-[720px] grid-cols-[210px_110px_100px_100px_100px_1fr] border-t border-white/[0.07] px-3 py-2.5 text-xs text-slate-300"><span>{new Date(reading.timestamp).toLocaleString()}</span><span>{reading.active_power_kw.toFixed(3)} kW</span><span>{reading.voltage_v.toFixed(1)} V</span><span>{reading.current_a.toFixed(2)} A</span><span className="capitalize">{reading.source}</span><span className="capitalize">{reading.quality}</span></div>)}</div>{readingCursor ? <div className="mt-4 text-center"><Button variant="outline" disabled={readingsLoading} onClick={() => void loadReadings(true)}>{readingsLoading ? <RefreshCw className="animate-spin" /> : null}Load more</Button></div> : <p className="mt-3 text-center text-xs text-slate-500">End of the selected period.</p>}</> : <div className="py-10 text-center text-sm text-slate-500">{readingsLoading ? 'Loading raw readings...' : 'No raw readings in this period.'}</div>}
          </CardContent>
        </Card>

        <Card className="rounded-lg border-white/10 bg-[#111827]">
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><Upload className="h-4 w-4 text-cyan-400" />Import CSV history</CardTitle><p className="text-xs text-slate-400">UTF-8 CSV, maximum 5 MB and 10,000 rows. Required columns: timestamp with timezone and active_power_kw. GAP and Datetime aliases are accepted.</p></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 rounded-lg border border-cyan-400/15 bg-cyan-400/[0.035] p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-medium text-cyan-100">Need forecast-ready demo history?</p><p className="mt-1 text-xs leading-5 text-slate-400">Download 337 hourly points covering the latest 336 complete hours, then preview and import them below.</p></div><a className={buttonVariants({ size: 'sm', variant: 'outline' })} download href="/samples/forecast-ready"><Download className="h-4 w-4" />Download sample</a></div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center"><input accept=".csv,text/csv" className="block min-w-0 flex-1 text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-slate-700 file:px-3 file:py-2 file:text-white" onChange={(event) => event.target.files?.[0] && previewCsv(event.target.files[0])} type="file" /><Button disabled={!csvFile || !preview?.valid_rows || importing} onClick={importCsv}>{importing ? 'Importing...' : 'Import validated rows'}</Button></div>
            {preview && <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-slate-300"><p className="flex items-center gap-1.5 text-emerald-300"><FileCheck2 className="h-4 w-4" />{preview.valid_rows} valid, {preview.rejected_rows} rejected</p><p className="mt-2 text-slate-400">Mapped columns: {preview.mapped_columns.join(', ')}</p>{preview.errors.length > 0 && <div className="mt-3 max-h-28 overflow-y-auto text-amber-200">{preview.errors.map((item) => <p key={`${item.row}-${item.message}`}>Row {item.row}: {item.message}</p>)}</div>}</div>}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
