'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  Check,
  CheckCircle2,
  Clock3,
  Loader2,
  RotateCcw,
  Settings,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { alertsApi } from '@/lib/api';
import { parseDate } from '@/lib/utils';
import type { Alert, AlertConfig } from '@/types';


type AlertStateFilter = 'all' | 'open' | 'acknowledged' | 'resolved';

const severityStyles: Record<Alert['severity'], string> = {
  low: 'border-blue-400/30 text-blue-300',
  medium: 'border-amber-400/30 text-amber-300',
  high: 'border-orange-400/30 text-orange-300',
  critical: 'border-red-400/30 text-red-300',
};

function Evidence({ alert }: { alert: Alert }) {
  const evidence = alert.evidence;
  if (typeof evidence.observed_kw === 'number' && typeof evidence.threshold_kw === 'number') {
    return <p className="border-l-2 border-amber-400/50 pl-3 text-xs text-slate-400">Measured {evidence.observed_kw.toFixed(3)} kW against {evidence.threshold_kw.toFixed(3)} kW. Source: {String(evidence.source || 'unknown')}.</p>;
  }
  if (typeof evidence.age_minutes === 'number') {
    return <p className="border-l-2 border-rose-400/50 pl-3 text-xs text-slate-400">Last push sample was {evidence.age_minutes.toFixed(1)} minutes old. Rule threshold: {String(evidence.missing_data_minutes)} minutes.</p>;
  }
  return null;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [config, setConfig] = useState<AlertConfig>({
    high_consumption_threshold: 3,
    cooldown_minutes: 60,
    missing_data_minutes: 60,
  });
  const [filter, setFilter] = useState<AlertStateFilter>('all');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [updating, setUpdating] = useState<string | null>(null);

  const loadAlerts = useCallback(async (selected: AlertStateFilter) => {
    setLoading(true);
    try {
      const nextAlerts = await alertsApi.getAlerts(selected);
      setAlerts(nextAlerts.sort((a, b) => parseDate(b.created_at).getTime() - parseDate(a.created_at).getTime()));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not load alerts.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.all([
      loadAlerts('all'),
      alertsApi.getConfig().then(setConfig).catch(() => toast.error('Could not load alert rules.')),
    ]);
  }, [loadAlerts]);

  const selectFilter = (selected: AlertStateFilter) => {
    setFilter(selected);
    void loadAlerts(selected);
  };

  const updateLifecycle = async (alert: Alert, action: 'acknowledge' | 'resolve' | 'reopen') => {
    setUpdating(alert.id);
    try {
      if (action === 'acknowledge') await alertsApi.acknowledgeAlert(alert.id);
      if (action === 'resolve') await alertsApi.resolveAlert(alert.id);
      if (action === 'reopen') await alertsApi.reopenAlert(alert.id);
      await loadAlerts(filter);
      toast.success(action === 'acknowledge' ? 'Alert acknowledged.' : action === 'resolve' ? 'Alert resolved.' : 'Alert reopened.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not update the alert.');
    } finally {
      setUpdating(null);
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
      setConfig(await alertsApi.configureAlerts(config));
      toast.success('Alert rules saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not save alert rules.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <header>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Bell className="h-6 w-6 text-blue-400" />Alerts</h1>
          <p className="mt-1 text-sm text-slate-400">Meter-rule incidents with measured evidence</p>
        </header>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section className="space-y-4">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Alert state">
              {(['all', 'open', 'acknowledged', 'resolved'] as const).map((state) => (
                <Button key={state} variant={filter === state ? 'default' : 'outline'} size="sm" onClick={() => selectFilter(state)} className="capitalize">{state}</Button>
              ))}
            </div>

            {loading ? (
              <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-blue-400" /></div>
            ) : alerts.length ? (
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <Card key={alert.id} className="rounded-lg border-white/[0.08] bg-[#111827]/80">
                    <CardContent className="flex gap-3 p-4">
                      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
                      <div className="min-w-0 flex-1 space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div><p className="text-sm font-semibold text-white">{alert.title}</p><p className="mt-1 text-sm leading-6 text-slate-400">{alert.message}</p></div>
                          <div className="flex gap-2"><Badge variant="outline" className={severityStyles[alert.severity]}>{alert.severity}</Badge><Badge variant="outline" className="border-white/15 capitalize text-slate-300">{alert.state}</Badge></div>
                        </div>
                        <Evidence alert={alert} />
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                          <span className="mr-2">{parseDate(alert.created_at).toLocaleString()}</span>
                          {alert.state === 'open' ? <Button size="sm" variant="ghost" disabled={updating === alert.id} onClick={() => void updateLifecycle(alert, 'acknowledge')}><Check className="h-3.5 w-3.5" />Acknowledge</Button> : null}
                          {alert.state !== 'resolved' ? <Button size="sm" variant="ghost" disabled={updating === alert.id} onClick={() => void updateLifecycle(alert, 'resolve')}><CheckCircle2 className="h-3.5 w-3.5" />Resolve</Button> : null}
                          {alert.state === 'resolved' ? <Button size="sm" variant="ghost" disabled={updating === alert.id} onClick={() => void updateLifecycle(alert, 'reopen')}><RotateCcw className="h-3.5 w-3.5" />Reopen</Button> : null}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="border-y border-white/10 py-16 text-center"><CheckCircle2 className="mx-auto h-9 w-9 text-emerald-400" /><p className="mt-3 font-medium text-white">No {filter === 'all' ? '' : `${filter} `}alerts</p></div>
            )}
          </section>

          <Card className="h-fit rounded-lg border-white/[0.08] bg-[#111827]/80">
            <CardHeader><CardTitle className="flex items-center gap-2 text-base text-white"><Settings className="h-4 w-4 text-blue-400" />Alert rules</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2"><Label htmlFor="threshold">High load threshold (kW)</Label><Input id="threshold" type="number" min="0.1" max="20" step="0.1" value={config.high_consumption_threshold} onChange={(event) => setConfig((value) => ({ ...value, high_consumption_threshold: Number(event.target.value) }))} /></div>
              <div className="space-y-2"><Label htmlFor="cooldown">Repeat cooldown (minutes)</Label><Input id="cooldown" type="number" min="5" max="1440" step="5" value={config.cooldown_minutes} onChange={(event) => setConfig((value) => ({ ...value, cooldown_minutes: Number(event.target.value) }))} /></div>
              <div className="space-y-2"><Label htmlFor="missing-data">Missing push data after (minutes)</Label><Input id="missing-data" type="number" min="5" max="10080" step="5" value={config.missing_data_minutes} onChange={(event) => setConfig((value) => ({ ...value, missing_data_minutes: Number(event.target.value) }))} /></div>
              <p className="text-sm text-slate-300">Delivery: in-app only</p>
              <p className="flex gap-2 text-xs leading-5 text-slate-500"><Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0" />High load is checked on ingestion. Missing push data is checked by the alert worker.</p>
              <Button className="w-full" onClick={() => void save()} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}Save rules</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
