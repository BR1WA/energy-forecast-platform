'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Loader2,
  Mail,
  RotateCcw,
  Settings,
  Sparkles,
  X,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { alertsApi, recommendationsApi } from '@/lib/api';
import { parseDate } from '@/lib/utils';
import type { Alert, AlertConfig, Recommendation } from '@/types';

type ActionFilter = 'attention' | 'monitoring' | 'completed' | 'all';
type EmailCapabilityState =
  | { status: 'loading' }
  | { status: 'available' }
  | { status: 'unavailable'; reason: 'mail_disabled' | 'email_unverified' }
  | { status: 'unknown' };

const severityStyles: Record<Alert['severity'], string> = {
  low: 'border-blue-400/30 text-blue-300',
  medium: 'border-amber-400/30 text-amber-300',
  high: 'border-orange-400/30 text-orange-300',
  critical: 'border-red-400/30 text-red-300',
};

function Evidence({ alert }: { alert: Alert }) {
  const evidence = alert.evidence;
  if (typeof evidence.observed_kw === 'number' && typeof evidence.threshold_kw === 'number') {
    return <p className="border-l-2 border-amber-400/50 pl-3 text-xs leading-5 text-slate-400">Measured {evidence.observed_kw.toFixed(3)} kW against the configured {evidence.threshold_kw.toFixed(3)} kW threshold. Source: {String(evidence.source || 'unknown')}.</p>;
  }
  if (typeof evidence.age_minutes === 'number') {
    return <p className="border-l-2 border-rose-400/50 pl-3 text-xs leading-5 text-slate-400">The latest push sample was {evidence.age_minutes.toFixed(1)} minutes old. The configured missing-data threshold is {String(evidence.missing_data_minutes)} minutes.</p>;
  }
  return null;
}

function RecommendationEvidence({ item }: { item: Recommendation }) {
  const observed = typeof item.evidence_json.observed_kw === 'number' ? item.evidence_json.observed_kw.toFixed(2) : null;
  const threshold = typeof item.evidence_json.threshold_kw === 'number' ? item.evidence_json.threshold_kw.toFixed(2) : null;
  if (!observed || !threshold) return null;
  return <p className="rounded border border-white/[0.06] bg-black/10 p-3 text-xs text-slate-400">Action evidence: {observed} kW measured against {threshold} kW.</p>;
}

function emailCapabilityFromConfig(config: AlertConfig): EmailCapabilityState {
  if (config.email_delivery_available) return { status: 'available' };
  if (config.email_delivery_unavailable_reason !== 'mail_disabled' && config.email_delivery_unavailable_reason !== 'email_unverified') {
    return { status: 'unknown' };
  }
  return {
    status: 'unavailable',
    reason: config.email_delivery_unavailable_reason,
  };
}

export default function ActionsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [config, setConfig] = useState<AlertConfig>({
    high_consumption_threshold: 3,
    cooldown_minutes: 60,
    missing_data_minutes: 60,
    email_enabled: false,
    email_delivery_available: false,
    email_delivery_unavailable_reason: null,
  });
  const [emailCapability, setEmailCapability] = useState<EmailCapabilityState>({ status: 'loading' });
  const [hasLoadedConfig, setHasLoadedConfig] = useState(false);
  const [filter, setFilter] = useState<ActionFilter>('attention');
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [recommendationsLoading, setRecommendationsLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [updatingAlert, setUpdatingAlert] = useState<string | null>(null);
  const [updatingRecommendation, setUpdatingRecommendation] = useState<number | null>(null);

  const load = useCallback(async () => {
    setAlertsLoading(true);
    setRecommendationsLoading(true);
    setEmailCapability({ status: 'loading' });

    const alertsRequest = alertsApi.getAlerts('all')
      .then((nextAlerts) => setAlerts(nextAlerts.sort((a, b) => parseDate(b.created_at).getTime() - parseDate(a.created_at).getTime())))
      .catch((error) => toast.error(error instanceof Error ? error.message : 'Could not load incidents.'))
      .finally(() => setAlertsLoading(false));
    const recommendationsRequest = recommendationsApi.getAll(true)
      .then(setRecommendations)
      .catch((error) => toast.error(error instanceof Error ? error.message : 'Could not load recommendations.'))
      .finally(() => setRecommendationsLoading(false));
    const configRequest = alertsApi.getConfig()
      .then((nextConfig) => {
        setConfig(nextConfig);
        setEmailCapability(emailCapabilityFromConfig(nextConfig));
        setHasLoadedConfig(true);
      })
      .catch(() => setEmailCapability({ status: 'unknown' }));

    await Promise.allSettled([alertsRequest, recommendationsRequest, configRequest]);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const recommendationByAlert = useMemo(() => {
    const linked = new Map<string, Recommendation>();
    for (const recommendation of recommendations) {
      if (recommendation.alert_id != null) linked.set(String(recommendation.alert_id), recommendation);
    }
    return linked;
  }, [recommendations]);

  const loadedAlertIds = useMemo(() => new Set(alerts.map((alert) => alert.id)), [alerts]);
  const unlinkedRecommendations = useMemo(
    () => recommendations.filter((item) => item.alert_id == null || !loadedAlertIds.has(String(item.alert_id))),
    [loadedAlertIds, recommendations],
  );

  const visibleAlerts = useMemo(() => alerts.filter((alert) => {
    const recommendation = recommendationByAlert.get(alert.id);
    if (filter === 'monitoring') return alert.state !== 'resolved';
    if (filter === 'completed') return alert.state === 'resolved' && recommendation?.status !== 'open';
    if (filter === 'attention') return alert.state !== 'resolved' || recommendation?.status === 'open';
    return true;
  }), [alerts, filter, recommendationByAlert]);

  const visibleUnlinked = useMemo(() => unlinkedRecommendations.filter((item) => {
    if (filter === 'attention' || filter === 'monitoring') return item.status === 'open';
    if (filter === 'completed') return item.status !== 'open';
    return true;
  }), [filter, unlinkedRecommendations]);

  const attentionCount = useMemo(() => {
    const alertIds = new Set(alerts.filter((alert) => (
      alert.state !== 'resolved' || recommendationByAlert.get(alert.id)?.status === 'open'
    )).map((alert) => alert.id));
    return alertIds.size + unlinkedRecommendations.filter((item) => item.status === 'open').length;
  }, [alerts, recommendationByAlert, unlinkedRecommendations]);

  const updateAlertLifecycle = async (alert: Alert, action: 'acknowledge' | 'resolve' | 'reopen') => {
    setUpdatingAlert(alert.id);
    try {
      if (action === 'acknowledge') await alertsApi.acknowledgeAlert(alert.id);
      if (action === 'resolve') await alertsApi.resolveAlert(alert.id);
      if (action === 'reopen') await alertsApi.reopenAlert(alert.id);
      await load();
      toast.success(action === 'acknowledge' ? 'Incident acknowledged.' : action === 'resolve' ? 'Incident resolved.' : 'Incident reopened.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not update the incident.');
    } finally {
      setUpdatingAlert(null);
    }
  };

  const updateRecommendation = async (item: Recommendation, status: Recommendation['status']) => {
    setUpdatingRecommendation(item.id);
    try {
      await recommendationsApi.updateStatus(item.id, status);
      await load();
      toast.success(status === 'completed' ? 'Action marked complete.' : status === 'dismissed' ? 'Action dismissed.' : 'Action reopened.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not update the action.');
    } finally {
      setUpdatingRecommendation(null);
    }
  };

  const saveRules = async () => {
    if (!hasLoadedConfig) {
      toast.error('Action rules are temporarily unavailable.');
      return;
    }
    const values = [config.high_consumption_threshold, config.cooldown_minutes, config.missing_data_minutes];
    if (values.some((value) => !Number.isFinite(Number(value))) || config.high_consumption_threshold <= 0 || config.cooldown_minutes < 5 || config.missing_data_minutes < 5) {
      toast.error('Use a positive threshold and intervals of at least five minutes.');
      return;
    }
    setSaving(true);
    try {
      const nextConfig = await alertsApi.configureAlerts(config);
      setConfig(nextConfig);
      setEmailCapability(emailCapabilityFromConfig(nextConfig));
      toast.success('Action rules saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not save action rules.');
    } finally {
      setSaving(false);
    }
  };

  const renderRecommendation = (item: Recommendation, incidentResolved = false) => {
    const isOpen = item.status === 'open';
    const isUpdating = updatingRecommendation === item.id;
    return (
      <div className="space-y-3 rounded-lg border border-cyan-400/15 bg-cyan-400/[0.035] p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-cyan-100"><Sparkles className="h-4 w-4 text-cyan-400" />{item.title}</p>
            {incidentResolved && isOpen ? <p className="mt-1 text-xs font-medium text-amber-300">Follow-up remains open although the measured incident has ended.</p> : null}
          </div>
          <Badge variant="outline" className="border-cyan-400/20 capitalize text-cyan-200">{item.status}</Badge>
        </div>
        <p className="text-sm leading-6 text-slate-300">{item.message}</p>
        <RecommendationEvidence item={item} />
        {item.estimated_excess_cost_per_hour_mad != null ? <p className="text-xs text-amber-300">Estimated excess-load cost: {item.estimated_excess_cost_per_hour_mad.toFixed(4)} MAD/hour at the configured tariff. This is not a guaranteed saving.</p> : null}
        <div className="flex flex-wrap gap-2">
          {isOpen ? (
            <>
              <Button size="sm" disabled={isUpdating} onClick={() => void updateRecommendation(item, 'completed')}><CheckCircle2 className="h-4 w-4" />Mark complete</Button>
              <Button size="sm" variant="outline" disabled={isUpdating} onClick={() => void updateRecommendation(item, 'dismissed')}><X className="h-4 w-4" />Dismiss</Button>
            </>
          ) : (
            <Button size="sm" variant="outline" disabled={isUpdating} onClick={() => void updateRecommendation(item, 'open')}><RotateCcw className="h-4 w-4" />Reopen action</Button>
          )}
        </div>
      </div>
    );
  };

  const contentLoading = alertsLoading || recommendationsLoading;
  const emailStatusMessage = emailCapability.status === 'loading'
    ? 'Checking email delivery availability...'
    : emailCapability.status === 'unknown'
      ? 'Email delivery status is temporarily unavailable.'
      : emailCapability.status === 'unavailable'
        ? emailCapability.reason === 'email_unverified'
          ? 'Verify your email to enable email alerts.'
          : 'Email delivery is unavailable.'
        : config.email_enabled
          ? 'Enabled for newly created critical incidents.'
          : 'Off. Opt in to receive newly created critical incidents by email.';

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-white"><CircleAlert className="h-6 w-6 text-cyan-400" />Actions</h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-400">Measured incidents and their evidence-backed follow-up actions in one workflow.</p>
          </div>
          <div className="rounded-md border border-amber-400/20 bg-amber-400/[0.05] px-3 py-2 text-sm text-amber-200">{attentionCount} need attention</div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section className="space-y-4">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Action state">
              {(['attention', 'monitoring', 'completed', 'all'] as const).map((state) => (
                <Button key={state} variant={filter === state ? 'default' : 'outline'} size="sm" onClick={() => setFilter(state)} className="capitalize">{state}</Button>
              ))}
            </div>

            {contentLoading && alerts.length === 0 && recommendations.length === 0 ? (
              <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /></div>
            ) : visibleAlerts.length || visibleUnlinked.length ? (
              <div className="space-y-4">
                {visibleAlerts.map((alert) => {
                  const recommendation = recommendationByAlert.get(alert.id);
                  return (
                    <Card id={`action-${alert.id}`} key={alert.id} className="scroll-mt-6 rounded-lg border-white/[0.08] bg-[#111827]/80 target:border-red-400/60">
                      <CardContent className="space-y-4 p-4">
                        <div className="flex gap-3">
                          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
                          <div className="min-w-0 flex-1 space-y-3">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div><p className="text-sm font-semibold text-white">{alert.title}</p><p className="mt-1 text-sm leading-6 text-slate-400">{alert.message}</p></div>
                              <div className="flex gap-2"><Badge variant="outline" className={severityStyles[alert.severity]}>{alert.severity}</Badge><Badge variant="outline" className="border-white/15 capitalize text-slate-300">{alert.state}</Badge></div>
                            </div>
                            <Evidence alert={alert} />
                            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                              <span className="mr-2">{parseDate(alert.created_at).toLocaleString()}</span>
                              {alert.state === 'open' ? <Button size="sm" variant="ghost" disabled={updatingAlert === alert.id} onClick={() => void updateAlertLifecycle(alert, 'acknowledge')}><Check className="h-3.5 w-3.5" />Acknowledge</Button> : null}
                              {alert.state !== 'resolved' ? <Button size="sm" variant="ghost" disabled={updatingAlert === alert.id} onClick={() => void updateAlertLifecycle(alert, 'resolve')}><CheckCircle2 className="h-3.5 w-3.5" />Resolve incident</Button> : null}
                              {alert.state === 'resolved' ? <Button size="sm" variant="ghost" disabled={updatingAlert === alert.id} onClick={() => void updateAlertLifecycle(alert, 'reopen')}><RotateCcw className="h-3.5 w-3.5" />Reopen incident</Button> : null}
                            </div>
                          </div>
                        </div>
                        {recommendation ? renderRecommendation(recommendation, alert.state === 'resolved') : <p className="border-t border-white/10 pt-3 text-xs text-slate-500">No separate follow-up action was generated for this incident.</p>}
                      </CardContent>
                    </Card>
                  );
                })}
                {visibleUnlinked.map((item) => <Card key={`recommendation-${item.id}`} className="rounded-lg border-white/[0.08] bg-[#111827]/80"><CardContent className="p-4">{renderRecommendation(item)}</CardContent></Card>)}
              </div>
            ) : (
              <div className="border-y border-white/10 py-16 text-center"><CheckCircle2 className="mx-auto h-9 w-9 text-emerald-400" /><p className="mt-3 font-medium text-white">Nothing in {filter}</p><p className="mt-2 text-sm text-slate-500">New measured incidents and follow-up actions will appear here.</p></div>
            )}
          </section>

          <Card className="h-fit rounded-lg border-white/[0.08] bg-[#111827]/80">
            <CardHeader><CardTitle className="flex items-center gap-2 text-base text-white"><Settings className="h-4 w-4 text-blue-400" />Action rules</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2"><Label htmlFor="threshold">High load threshold (kW)</Label><Input disabled={!hasLoadedConfig} id="threshold" type="number" min="0.1" max="20" step="0.1" value={config.high_consumption_threshold} onChange={(event) => setConfig((value) => ({ ...value, high_consumption_threshold: Number(event.target.value) }))} /></div>
              <div className="space-y-2"><Label htmlFor="cooldown">Repeat cooldown (minutes)</Label><Input disabled={!hasLoadedConfig} id="cooldown" type="number" min="5" max="1440" step="5" value={config.cooldown_minutes} onChange={(event) => setConfig((value) => ({ ...value, cooldown_minutes: Number(event.target.value) }))} /></div>
              <div className="space-y-2"><Label htmlFor="missing-data">Missing push data after (minutes)</Label><Input disabled={!hasLoadedConfig} id="missing-data" type="number" min="5" max="10080" step="5" value={config.missing_data_minutes} onChange={(event) => setConfig((value) => ({ ...value, missing_data_minutes: Number(event.target.value) }))} /></div>
              <div className="space-y-3 border-t border-white/10 pt-4">
                <div className="flex items-start gap-3">
                  <input aria-describedby="critical-email-status" checked={config.email_enabled} className="mt-1 h-4 w-4 accent-blue-500" disabled={emailCapability.status !== 'available'} id="critical-email-enabled" onChange={(event) => setConfig((value) => ({ ...value, email_enabled: event.target.checked }))} type="checkbox" />
                  <div><Label className="flex items-center gap-2" htmlFor="critical-email-enabled"><Mail className="h-4 w-4 text-blue-400" />Email critical incidents</Label><p className="mt-1 text-xs leading-5 text-slate-500">All incidents remain available in the app.</p></div>
                </div>
                <p id="critical-email-status" className={emailCapability.status === 'available' || emailCapability.status === 'loading' ? 'text-xs text-slate-400' : 'text-xs text-amber-300'}>{emailStatusMessage}</p>
              </div>
              <p className="flex gap-2 text-xs leading-5 text-slate-500"><Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0" />High load is checked on ingestion. Missing push data is checked by the alert worker.</p>
              <Button className="w-full" onClick={() => void saveRules()} disabled={saving || !hasLoadedConfig}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}Save rules</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
