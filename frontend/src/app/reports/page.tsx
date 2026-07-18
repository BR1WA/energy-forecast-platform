'use client';

import { useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Download, FileText, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { analyticsApi, consumptionApi } from '@/lib/api';
import type { AnalyticsSummary } from '@/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'pdf' | 'csv' | null>(null);
  const load = async () => { setLoading(true); try { setSummary(await analyticsApi.getSummary()); } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to load report data.'); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);
  const exportPdf = async () => { setExporting('pdf'); try { saveBlob(await analyticsApi.downloadReportPDF(), 'energy-forecast-report.pdf'); } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to export the report.'); } finally { setExporting(null); } };
  const exportCsv = async () => { setExporting('csv'); try { saveBlob(await consumptionApi.exportCsv(), 'energy-consumption.csv'); } catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to export consumption data.'); } finally { setExporting(null); } };
  return <AppLayout><div className="mx-auto max-w-6xl space-y-6"><header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h1 className="flex items-center gap-2 text-2xl font-bold text-white"><FileText className="h-6 w-6 text-indigo-400" />Reports</h1><p className="mt-1 text-sm text-slate-400">Exports contain only persisted forecasts and measured consumption.</p></div><Button variant="outline" onClick={load} disabled={loading} className="border-white/10 text-slate-200"><RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</Button></header><div className="grid gap-4 md:grid-cols-4"><Fact label="Forecasts" value={summary?.total_forecasts ?? 0} /><Fact label="Alerts" value={summary?.total_alerts ?? 0} /><Fact label="Unacknowledged" value={summary?.unacknowledged_alerts ?? 0} /><Fact label="Average forecast peak" value={summary?.avg_peak_power === null || summary?.avg_peak_power === undefined ? 'Not available' : `${summary.avg_peak_power.toFixed(3)} kW`} /></div><div className="grid gap-6 lg:grid-cols-3"><Card className="border-white/10 bg-[#111827]/80 lg:col-span-2"><CardHeader><CardTitle className="text-base text-white">Recent persisted forecasts</CardTitle><CardDescription>Model and peak values are shown only after a forecast was saved.</CardDescription></CardHeader><CardContent>{loading ? <p className="py-8 text-sm text-slate-400">Loading report data...</p> : summary?.recent_forecasts.length ? <div className="divide-y divide-white/10">{summary.recent_forecasts.map((forecast) => <div key={forecast.id} className="flex items-center justify-between py-3 text-sm"><div><p className="font-medium text-white">{forecast.model_name}</p><p className="text-xs text-slate-500">{forecast.created_at ? new Date(forecast.created_at).toLocaleString() : 'Unknown time'}</p></div><span className="text-slate-300">{forecast.peak_power == null ? 'Peak unavailable' : `${forecast.peak_power.toFixed(3)} kW`}</span></div>)}</div> : <p className="py-8 text-sm text-slate-400">Run a forecast after importing or ingesting enough readings to generate a report.</p>}</CardContent></Card><Card className="border-white/10 bg-[#111827]/80"><CardHeader><CardTitle className="text-base text-white">Exports</CardTitle><CardDescription>Generated directly from your account data.</CardDescription></CardHeader><CardContent className="space-y-3"><Button className="w-full justify-between" onClick={exportPdf} disabled={exporting !== null}>Forecast PDF <Download className="h-4 w-4" /></Button><Button variant="outline" className="w-full justify-between border-white/10 text-slate-200" onClick={exportCsv} disabled={exporting !== null}>Consumption CSV <Download className="h-4 w-4" /></Button><p className="text-xs leading-5 text-slate-500">Forecast exports disclose the model and prediction values. Consumption exports use the configured tariff calculation.</p></CardContent></Card></div></div></AppLayout>;
}

function Fact({ label, value }: { label: string; value: string | number }) { return <Card className="border-white/10 bg-[#111827]/80"><CardContent className="p-4"><p className="text-xs font-medium uppercase text-slate-400">{label}</p><p className="mt-3 text-xl font-semibold text-white">{value}</p></CardContent></Card>; }
