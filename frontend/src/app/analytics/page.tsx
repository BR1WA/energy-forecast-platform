'use client';

import { useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { analyticsApi } from '@/lib/api';
import { AnalyticsSummary } from '@/types';
import { BarChart3, FileText, Loader2, Activity, AlertTriangle, Cpu } from 'lucide-react';
import { toast } from 'sonner';

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    analyticsApi
      .getSummary()
      .then((data) => setSummary(data as AnalyticsSummary))
      .catch(() => toast.error('Could not load analytics.'))
      .finally(() => setLoading(false));
  }, []);

  const exportReport = async () => {
    setExporting(true);
    try {
      downloadBlob(await analyticsApi.downloadReportPDF(), `energy-report-${new Date().toISOString().slice(0, 10)}.pdf`);
    } catch {
      toast.error('Could not export the report.');
    } finally {
      setExporting(false);
    }
  };

  const modelEntries = Object.entries(summary?.models_used ?? {});
  const forecasts = summary?.recent_forecasts ?? [];

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6 p-2">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
              <BarChart3 className="h-6 w-6 text-blue-400" />
              Analytics
            </h1>
            <p className="mt-1 text-sm text-slate-400">Forecast activity and alert history recorded for your account.</p>
          </div>
          <Button onClick={exportReport} disabled={exporting} className="gap-2 bg-blue-600 text-white hover:bg-blue-500">
            {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
            Export PDF
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Forecasts run" value={summary?.total_forecasts} icon={BarChart3} loading={loading} />
          <Metric label="Recorded alerts" value={summary?.total_alerts} icon={AlertTriangle} loading={loading} />
          <Metric label="Unacknowledged alerts" value={summary?.unacknowledged_alerts} icon={Activity} loading={loading} />
          <Metric label="Average forecast peak" value={summary?.avg_peak_power == null ? null : `${summary.avg_peak_power.toFixed(2)} kW`} icon={Cpu} loading={loading} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="glass-card border-white/[0.06]">
            <CardHeader>
              <CardTitle className="text-base text-white">Forecast models used</CardTitle>
            </CardHeader>
            <CardContent>
              {modelEntries.length ? (
                <div className="space-y-3">
                  {modelEntries.map(([model, count]) => (
                    <div key={model} className="flex items-center justify-between border-b border-white/[0.06] pb-3 last:border-0 last:pb-0">
                      <span className="text-sm text-slate-200">{model}</span>
                      <Badge variant="outline" className="border-blue-400/30 text-blue-300">{count} request{count === 1 ? '' : 's'}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty text="No forecasts have been recorded yet." />
              )}
            </CardContent>
          </Card>

          <Card className="glass-card border-white/[0.06]">
            <CardHeader>
              <CardTitle className="text-base text-white">Recent forecasts</CardTitle>
            </CardHeader>
            <CardContent>
              {forecasts.length ? (
                <div className="space-y-3">
                  {forecasts.map((forecast) => (
                    <div key={forecast.id} className="flex items-center justify-between gap-3 border-b border-white/[0.06] pb-3 last:border-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-200">{forecast.model_name}</p>
                        <p className="text-xs text-slate-500">{forecast.created_at ? new Date(forecast.created_at).toLocaleString() : 'Timestamp unavailable'}</p>
                      </div>
                      <span className="shrink-0 text-sm text-slate-300">{forecast.peak_power == null ? 'Peak unavailable' : `${forecast.peak_power.toFixed(2)} kW`}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty text="Run a forecast after importing enough readings to populate this history." />
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="glass-card border-white/[0.06]">
          <CardHeader><CardTitle className="text-base text-white">Outcome analysis</CardTitle></CardHeader>
          <CardContent><Empty text="Actual-versus-forecast charts appear only after forecasts can be matched to later measured readings." /></CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}

function Metric({ label, value, icon: Icon, loading }: { label: string; value: string | number | null | undefined; icon: typeof BarChart3; loading: boolean }) {
  return <Card className="glass-card border-white/[0.06]"><CardContent className="p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-slate-400">{label}</p><p className="mt-1 text-xl font-semibold text-white">{loading ? <Loader2 className="h-5 w-5 animate-spin text-slate-500" /> : value ?? 'Not available'}</p></div><Icon className="h-5 w-5 text-blue-400" /></div></CardContent></Card>;
}

function Empty({ text }: { text: string }) {
  return <p className="py-5 text-sm text-slate-400">{text}</p>;
}
