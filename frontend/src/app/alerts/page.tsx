'use client';

import { useEffect, useMemo, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertTriangle, Bell, CheckCircle2, Clock3, Loader2, Settings, Zap } from 'lucide-react';
import { alertsApi } from '@/lib/api';
import { Alert, AlertConfig } from '@/types';
import { parseDate } from '@/lib/utils';
import { toast } from 'sonner';

const severityStyles: Record<Alert['severity'], string> = {
  low: 'border-blue-400/30 text-blue-300',
  medium: 'border-amber-400/30 text-amber-300',
  high: 'border-orange-400/30 text-orange-300',
  critical: 'border-red-400/30 text-red-300',
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [config, setConfig] = useState<AlertConfig>({ high_consumption_threshold: 3, cooldown_minutes: 60, missing_data_minutes: 60, notification_email: true });
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [nextAlerts, nextConfig] = await Promise.all([alertsApi.getAlerts(), alertsApi.getConfig()]);
      setAlerts(nextAlerts.sort((a, b) => parseDate(b.created_at).getTime() - parseDate(a.created_at).getTime()));
      setConfig(nextConfig);
    } catch {
      toast.error('Could not load alerts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const visibleAlerts = useMemo(() => filter === 'all' ? alerts : alerts.filter((alert) => !alert.is_read), [alerts, filter]);
  const unread = alerts.filter((alert) => !alert.is_read).length;

  const acknowledge = async (id: string) => {
    try {
      await alertsApi.acknowledgeAlert(id);
      setAlerts((items) => items.map((alert) => alert.id === id ? { ...alert, is_read: true } : alert));
    } catch {
      toast.error('Could not acknowledge the alert.');
    }
  };

  const save = async () => {
    const values = [config.high_consumption_threshold, config.cooldown_minutes, config.missing_data_minutes];
    if (values.some((value) => !Number.isFinite(Number(value))) || config.high_consumption_threshold <= 0 || config.cooldown_minutes < 5 || config.missing_data_minutes < 5) {
      toast.error('Use a positive threshold and intervals of at least five minutes.');
      return;
    }
    setSaving(true);
    try {
      const saved = await alertsApi.configureAlerts(config);
      setConfig(saved);
      toast.success('Alert settings saved.');
    } catch {
      toast.error('Could not save alert settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6 p-2">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Bell className="h-6 w-6 text-blue-400" />Alerts</h1><p className="mt-1 text-sm text-slate-400">Evidence-backed alerts from your meter data.</p></div>
          <Badge variant="outline" className="w-fit border-blue-400/30 text-blue-300">{unread} unacknowledged</Badge>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section className="space-y-4">
            <div className="flex gap-2"><Button variant={filter === 'all' ? 'default' : 'outline'} size="sm" onClick={() => setFilter('all')}>All</Button><Button variant={filter === 'unread' ? 'default' : 'outline'} size="sm" onClick={() => setFilter('unread')}>Unacknowledged</Button></div>
            {loading ? <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-blue-400" /></div> : visibleAlerts.length ? <div className="space-y-3">{visibleAlerts.map((alert) => <Card key={alert.id} className="glass-card border-white/[0.06]"><CardContent className="flex gap-3 p-4"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-sm font-semibold text-white">{alert.title}</p><p className="mt-1 text-sm text-slate-400">{alert.message || 'No additional details were recorded.'}</p></div><Badge variant="outline" className={severityStyles[alert.severity]}>{alert.severity}</Badge></div><div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500"><span>{parseDate(alert.created_at).toLocaleString()}</span>{!alert.is_read && <Button size="sm" variant="ghost" className="h-auto p-0 text-blue-300 hover:text-blue-200" onClick={() => void acknowledge(alert.id)}>Acknowledge</Button>}</div></div></CardContent></Card>)}</div> : <Card className="glass-card border-white/[0.06]"><CardContent className="flex flex-col items-center py-16 text-center"><CheckCircle2 className="h-9 w-9 text-emerald-400" /><p className="mt-3 font-medium text-white">No alerts to show</p><p className="mt-1 text-sm text-slate-400">New alerts appear only after a rule finds supporting meter evidence.</p></CardContent></Card>}
          </section>

          <Card className="glass-card h-fit border-white/[0.06]"><CardHeader><CardTitle className="flex items-center gap-2 text-base text-white"><Settings className="h-4 w-4 text-blue-400" />Alert rules</CardTitle></CardHeader><CardContent className="space-y-5"><div className="space-y-2"><Label htmlFor="threshold">High load threshold (kW)</Label><Input id="threshold" type="number" min="0.1" step="0.1" value={config.high_consumption_threshold} onChange={(event) => setConfig((value) => ({ ...value, high_consumption_threshold: Number(event.target.value) }))} /></div><div className="space-y-2"><Label htmlFor="cooldown">Repeat cooldown (minutes)</Label><Input id="cooldown" type="number" min="5" step="5" value={config.cooldown_minutes} onChange={(event) => setConfig((value) => ({ ...value, cooldown_minutes: Number(event.target.value) }))} /></div><div className="space-y-2"><Label htmlFor="missing-data">Missing push data after (minutes)</Label><Input id="missing-data" type="number" min="5" step="5" value={config.missing_data_minutes} onChange={(event) => setConfig((value) => ({ ...value, missing_data_minutes: Number(event.target.value) }))} /></div><p className="text-sm text-slate-300">Delivery: in-app alerts and recommendations.</p><p className="flex gap-2 text-xs leading-5 text-slate-500"><Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0" />High-load checks run when readings arrive. Missing-data checks run in the alert worker for push meters.</p><Button className="w-full gap-2 bg-blue-600 text-white hover:bg-blue-500" onClick={() => void save()} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}Save rules</Button></CardContent></Card>
        </div>
      </div>
    </AppLayout>
  );
}
