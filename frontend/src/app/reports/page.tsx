'use client';

import { useEffect, useState } from 'react';
import { Download, FileText, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { analyticsApi, consumptionApi } from '@/lib/api';
import type { AnalyticsSummary } from '@/types';


function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function methodLabel(method: string) {
  return method === 'global_tft' ? 'Global TFT' : method === 'seasonal_naive' ? 'Seasonal fallback' : method;
}

function Fact({ label, value }: { label: string; value: string | number }) {
  return <div className="border-l-2 border-indigo-400/60 pl-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-xl font-semibold text-white">{value}</p></div>;
}

export default function ReportsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [month, setMonth] = useState(currentMonth());
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'pdf' | 'csv' | null>(null);
  const latestForecast = summary?.recent_forecasts[0];

  const load = async () => {
    setLoading(true);
    try {
      setSummary(await analyticsApi.getSummary());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to load report data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const exportPdf = async () => {
    setExporting('pdf');
    try {
      saveBlob(await analyticsApi.downloadReportPDF(), 'energy-forecast-report.pdf');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to export the forecast report.');
    } finally {
      setExporting(null);
    }
  };

  const exportCsv = async () => {
    setExporting('csv');
    try {
      saveBlob(await consumptionApi.exportCsv(month), `energy-consumption-${month}.csv`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to export consumption data.');
    } finally {
      setExporting(null);
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><h1 className="flex items-center gap-2 text-2xl font-bold text-white"><FileText className="h-6 w-6 text-indigo-400" />Reports</h1><p className="mt-1 text-sm text-slate-400">Owned consumption, forecast, and incident records</p></div>
          <Button variant="outline" size="icon" onClick={() => void load()} disabled={loading} title="Refresh report summary" aria-label="Refresh report summary"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></Button>
        </header>

        <section className="grid gap-5 border-y border-white/10 bg-white/[0.025] px-4 py-5 sm:grid-cols-2 lg:grid-cols-5">
          <Fact label="Forecasts" value={summary?.total_forecasts ?? 0} />
          <Fact label="Open alerts" value={summary?.open_alerts ?? 0} />
          <Fact label="Resolved alerts" value={summary?.resolved_alerts ?? 0} />
          <Fact label="Open actions" value={summary?.open_recommendations ?? 0} />
          <Fact label="Average hourly peak" value={summary?.avg_forecast_peak_kwh == null ? 'Not available' : `${summary.avg_forecast_peak_kwh.toFixed(3)} kWh`} />
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="rounded-lg border-white/10 bg-[#111827]/80">
            <CardHeader><CardTitle className="text-base text-white">Recent persisted forecasts</CardTitle></CardHeader>
            <CardContent>
              {loading ? <p className="py-8 text-sm text-slate-400">Loading report data...</p> : summary?.recent_forecasts.length ? (
                <div className="divide-y divide-white/10">
                  {summary.recent_forecasts.map((forecast) => (
                    <div key={forecast.id} className="grid gap-2 py-3 text-sm sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:gap-5">
                      <div><p className="font-medium text-white">{methodLabel(forecast.method)} · {forecast.horizon_hours}h</p><p className="text-xs text-slate-500">{new Date(forecast.created_at).toLocaleString()}</p></div>
                      <span className="text-slate-300">{forecast.total_kwh == null ? 'Total unavailable' : `${forecast.total_kwh.toFixed(2)} kWh total`}</span>
                      <span className="text-slate-400">{forecast.peak_hourly_kwh == null ? 'Peak unavailable' : `${forecast.peak_hourly_kwh.toFixed(3)} kWh peak`}</span>
                    </div>
                  ))}
                </div>
              ) : <p className="py-8 text-sm text-slate-400">No product forecast has been persisted.</p>}
            </CardContent>
          </Card>

          <Card className="h-fit rounded-lg border-white/10 bg-[#111827]/80">
            <CardHeader><CardTitle className="text-base text-white">Exports</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div><p className="text-sm font-medium text-slate-200">Latest forecast</p><p className="mt-1 text-xs leading-5 text-slate-500">{latestForecast ? `${latestForecast.horizon_hours} target timestamps` : 'Persisted target timestamps'}, method, version, source, quantiles, tariff context, and limitations.</p><Button className="mt-3 w-full justify-between" onClick={exportPdf} disabled={exporting !== null || !summary?.total_forecasts}>Forecast PDF <Download className="h-4 w-4" /></Button></div>
              <div className="border-t border-white/10 pt-4"><Label htmlFor="report-month">Consumption month</Label><Input id="report-month" className="mt-2" type="month" value={month} onChange={(event) => setMonth(event.target.value)} /><Button variant="outline" className="mt-3 w-full justify-between border-white/10 text-slate-200" onClick={exportCsv} disabled={exporting !== null || !month}>Consumption CSV <Download className="h-4 w-4" /></Button></div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
