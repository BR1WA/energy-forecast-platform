'use client';

import React, { useState, useEffect, useCallback } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Zap, TrendingUp, Activity, Download, RefreshCw, Sparkles, AlertTriangle, CheckCircle, Upload } from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { consumptionApi, ingestionApi } from '@/lib/api';
import { toast } from 'sonner';

export default function ConsumptionPage() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    month: '', total_kwh: 0, total_cost: 0, peak_kw: 0, average_daily_kwh: 0, coverage_pct: 0,
    tariff: { currency: 'MAD', peak_rate: 0, off_peak_rate: 0, peak_start_hour: 0, peak_end_hour: 0 },
    budget: { target_mad: null as number | null, spent_mad: 0, remaining_mad: null as number | null, progress_pct: null as number | null, projected_mad: 0 },
    previous_month: { month: '', total_kwh: 0, total_cost: 0 }, comparison_pct: null as number | null,
  });
  const [current, setCurrent] = useState<{ kw: number; status: string; voltage?: number; intensity?: number; source?: string | null; age_seconds?: number | null; sub_metering_1?: number; sub_metering_2?: number; sub_metering_3?: number }>({
    kw: 0,
    status: 'normal',
    intensity: 0,
  });
  const [history, setHistory] = useState<Array<{ kw: number; timestamp: string; timeLabel: string }>>([]);
  const [meters, setMeters] = useState<Array<{ id: number; name: string }>>([]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvPreview, setCsvPreview] = useState<{ valid_rows: number; rejected_rows: number } | null>(null);
  const [importing, setImporting] = useState(false);
  const [timeframe, setTimeframe] = useState<'live' | 'day' | 'week' | 'month' | 'all'>('day');

  const fetchData = useCallback(async (selectedTimeframe = timeframe) => {
    try {
      setLoading(true);
      const [statsData, currentData, historyData] = await Promise.all([
        consumptionApi.getStatistics(),
        consumptionApi.getCurrent(),
        consumptionApi.getHistory(selectedTimeframe),
      ]);

      setStats(statsData);
      setCurrent(currentData);
      
      const formattedHistory = (historyData || []).map((item: any) => {
        const date = new Date(item.timestamp);
        const timeLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return {
          ...item,
          timeLabel,
        };
      });
      setHistory(formattedHistory);
    } catch (err) {
      console.error('Failed to load energy analytics:', err);
    } finally {
      setLoading(false);
    }
  }, [timeframe]);

  useEffect(() => {
    fetchData(timeframe);
    ingestionApi.getMeters().then(setMeters).catch(() => toast.error('Unable to load your meter for CSV import.'));
    const interval = setInterval(() => fetchData(timeframe), timeframe === 'live' ? 5000 : 30000);
    return () => clearInterval(interval);
  }, [fetchData, timeframe]);

  const previewCsv = async (file: File) => {
    if (!meters[0]) return;
    setCsvFile(file);
    setCsvPreview(null);
    try {
      const preview = await ingestionApi.previewCsv(meters[0].id, file);
      setCsvPreview(preview);
      if (preview.rejected_rows) toast.warning(`${preview.rejected_rows} row(s) need attention.`);
    } catch (error) {
      setCsvFile(null);
      toast.error(error instanceof Error ? error.message : 'Unable to validate this CSV file.');
    }
  };

  const importCsv = async () => {
    if (!meters[0] || !csvFile) return;
    setImporting(true);
    try {
      const result = await ingestionApi.importCsv(meters[0].id, csvFile);
      toast.success(`Imported ${result.accepted_rows} reading(s).`);
      if (result.rejected_rows) toast.warning(`${result.rejected_rows} row(s) were rejected.`);
      setCsvFile(null);
      setCsvPreview(null);
      fetchData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'CSV import failed.');
    } finally {
      setImporting(false);
    }
  };

  const handleExport = async () => {
    try {
      const blob = await consumptionApi.exportCsv();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `energy-${stats.month || 'current-month'}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export consumption data', err);
    }
  };

  const tariff = stats.tariff;

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
              <Sparkles className="text-indigo-400 w-8 h-8" /> Energy Consumption & Insights
            </h1>
            <p className="text-slate-400">Review measured consumption, tariff costs, and data coverage for this site.</p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => fetchData()}
              variant="outline"
              className="border-white/10 text-white hover:bg-white/5"
            >
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
            <Button
              onClick={handleExport}
              className="bg-indigo-600 hover:bg-indigo-500 text-white"
            >
              <Download className="mr-2 h-4 w-4" /> Export CSV
            </Button>
          </div>
        </div>

        <Card className="border-white/10 bg-[#111827]/80">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-white"><Upload className="h-4 w-4 text-cyan-400" />Import meter readings</CardTitle>
            <CardDescription className="text-xs text-slate-400">Upload a UTF-8 CSV with `timestamp` and `active_power_kw` columns. Legacy `GAP` and `Datetime` headers are accepted too.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 md:flex-row md:items-center">
            <input type="file" accept=".csv,text/csv" onChange={(event) => event.target.files?.[0] && previewCsv(event.target.files[0])} className="block w-full text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-slate-700 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-600 md:max-w-md" />
            {csvPreview && <span className="text-sm text-slate-400">{csvPreview.valid_rows} valid, {csvPreview.rejected_rows} rejected</span>}
            <Button onClick={importCsv} disabled={!csvFile || !csvPreview || importing} className="md:ml-auto">{importing ? 'Importing...' : 'Import CSV'}</Button>
          </CardContent>
        </Card>

        {/* Stats Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-400" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Current Power Usage</CardTitle>
              <Zap className="h-4 w-4 text-emerald-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {loading ? '...' : `${(current?.kw ?? 0).toFixed(3)} kW`}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Active feed: {current.voltage == null ? 'Voltage unavailable' : `${current.voltage.toFixed(1)}V`} / {current.intensity == null ? 'Current unavailable' : `${current.intensity.toFixed(2)}A`}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Source: {current.source || 'none'}{current.age_seconds !== undefined && current.age_seconds !== null ? `, ${current.age_seconds}s ago` : ''}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-amber-500 to-orange-400" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Peak Demand</CardTitle>
              <TrendingUp className="h-4 w-4 text-amber-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {loading ? '...' : `${(stats.peak_kw ?? 0).toFixed(3)} kW`}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Highest recorded load this month
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-indigo-500 to-blue-400" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Estimated Monthly Cost</CardTitle>
              <Activity className="h-4 w-4 text-indigo-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {loading ? '...' : `${tariff.currency} ${(stats.total_cost ?? 0).toFixed(2)}`}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Accumulated: {(stats?.total_kwh ?? 0).toFixed(2)} kWh
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-cyan-500 to-blue-400" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Month Comparison</CardTitle>
              <TrendingUp className="h-4 w-4 text-cyan-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">{stats.comparison_pct === null ? 'N/A' : `${stats.comparison_pct > 0 ? '+' : ''}${stats.comparison_pct}%`}</div>
              <p className="text-xs text-slate-500 mt-1">Previous month: {stats.previous_month.total_kwh.toFixed(2)} kWh</p>
            </CardContent>
          </Card>
        </div>

        {/* Recharts Historical Curve */}
        <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
          <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
            <div><CardTitle className="text-white text-base">Energy History</CardTitle><CardDescription className="text-slate-400 text-xs">Actual readings grouped for the selected period.</CardDescription></div>
            <div className="flex shrink-0 rounded-md border border-white/10 p-1">
              {(['live', 'day', 'week', 'month', 'all'] as const).map((range) => <button key={range} onClick={() => setTimeframe(range)} className={`rounded px-2 py-1 text-xs capitalize ${timeframe === range ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}>{range}</button>)}
            </div>
          </CardHeader>
          <CardContent>
            {loading && history.length === 0 ? (
              <div className="h-72 flex items-center justify-center text-slate-400">
                <RefreshCw className="mr-2 h-5 w-5 animate-spin" /> Loading historical charts...
              </div>
            ) : history.length === 0 ? (
              <div className="h-72 flex items-center justify-center text-slate-400">
                No active smart meter reading data available. Start the simulation to feed power values.
              </div>
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorKw" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="timeLabel" stroke="#94a3b8" fontSize={10} tickLine={false} />
                    <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} unit=" kW" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '0.375rem',
                      }}
                      labelStyle={{ color: '#fff' }}
                      itemStyle={{ color: '#818cf8' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="kw"
                      stroke="#6366f1"
                      fillOpacity={1}
                      fill="url(#colorKw)"
                      name="Load (kW)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* SaaS Sections Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* AI Insights & Timeline (Col 1) */}
          <div className="lg:col-span-1 space-y-6">
            {/* AI Insights Card */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-400" /> AI Insights
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-300">
                    The monthly projection is <strong>{tariff.currency} {stats.budget.projected_mad.toFixed(2)}</strong>, calculated from recorded intervals.
                  </p>
                </div>

                <div className="flex gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-300">
                    Data coverage for this month is <strong>{stats.coverage_pct.toFixed(1)}%</strong>. Long gaps are excluded from interval estimates.
                  </p>
                </div>

                <div className="flex gap-3 p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                  <Sparkles className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-300">
                    Appliance recommendations are unavailable until supported by device or sub-meter evidence.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Top Energy Events Card */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <Activity className="w-5 h-5 text-indigo-400" /> Top Energy Events
                </CardTitle>
                <CardDescription className="text-slate-400 text-xs">Real-time load spikes and status markers detected today.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 relative before:absolute before:inset-y-0 before:left-[17px] before:w-0.5 before:bg-white/5">
                <div className="flex gap-4 relative z-10">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 mt-1.5 shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                  <div>
                    <span className="text-[10px] font-mono text-slate-500">Latest reading</span>
                    <p className="text-xs font-semibold text-white">{current.source || 'No meter data'}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{current.age_seconds === null || current.age_seconds === undefined ? 'No reading timestamp is available.' : `Received ${current.age_seconds} seconds ago.`}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Appliance & Tariff breakdown (Col 2 & 3) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Appliance breakdown */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-white text-base">Sub-meter channels</CardTitle>
                <CardDescription className="text-slate-400 text-xs">Raw channel values are shown without inferring appliance identities.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-3">
                {[
                  { label: 'Sub-meter channel 1', value: current.sub_metering_1 },
                  { label: 'Sub-meter channel 2', value: current.sub_metering_2 },
                  { label: 'Sub-meter channel 3', value: current.sub_metering_3 },
                ].map((channel) => (
                  <div key={channel.label} className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <p className="text-xs text-slate-400">{channel.label}</p>
                    <p className="mt-1 text-lg font-semibold text-white">{channel.value == null ? 'Unavailable' : channel.value.toFixed(1)}</p>
                    <p className="text-xs text-slate-500">Raw meter value</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* site tariff card */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div>
                  <CardTitle className="text-white text-base">Site Tariff Status</CardTitle>
                  <CardDescription className="text-slate-400 text-xs">Costs are calculated from the peak and off-peak rates saved in site settings.</CardDescription>
                </div>
                <Badge className="bg-indigo-600 text-white text-[10px] uppercase font-semibold">{stats.month || 'Current month'}</Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-2 text-center text-xs">
                  <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10">
                    <div className="font-semibold text-white">Peak</div>
                    <div className="text-[10px] text-slate-400 mt-1">{tariff.peak_start_hour}:00-{tariff.peak_end_hour}:00</div>
                    <div className="text-[10px] text-amber-400 mt-0.5">{tariff.peak_rate.toFixed(4)} {tariff.currency}/kWh</div>
                  </div>
                  <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10"><div className="font-semibold text-white">Off-peak</div><div className="text-[10px] text-slate-400 mt-1">All remaining hours</div><div className="text-[10px] text-emerald-400 mt-0.5">{tariff.off_peak_rate.toFixed(4)} {tariff.currency}/kWh</div></div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>Data coverage for this month</span>
                    <span>{(stats.total_kwh ?? 0).toFixed(1)} kWh</span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-cyan-500" style={{ width: `${stats.coverage_pct}%` }} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
