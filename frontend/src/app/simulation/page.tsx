'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  Clock3,
  Database,
  History,
  Play,
  RotateCcw,
  Save,
  ShieldCheck,
  Square,
  TestTube2,
} from 'lucide-react';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { ConsumptionChart } from '@/components/consumption/consumption-chart';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { consumptionApi, simulationApi } from '@/lib/api';
import type { ConsumptionPeriodSummary, SimulationStatus } from '@/types';

function durationLabel(seconds: number) {
  const hours = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const minutes = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const remainder = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${hours}:${minutes}:${remainder}`;
}

function compactDate(value: string | null | undefined) {
  if (!value) return 'Not available';
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export default function SimulationPage() {
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [changingState, setChangingState] = useState<'start' | 'stop' | 'reset' | null>(null);
  const [summary, setSummary] = useState<ConsumptionPeriodSummary | null>(null);
  const [baseLoadKw, setBaseLoadKw] = useState(1.2);
  const [variationPercent, setVariationPercent] = useState(10);
  const isRunning = status?.is_running ?? false;

  const load = useCallback(async () => {
    try {
      const [nextStatus, period] = await Promise.all([
        simulationApi.getStatus(),
        consumptionApi.getPeriod('live'),
      ]);
      setStatus(nextStatus);
      setBaseLoadKw(nextStatus.base_load_kw);
      setVariationPercent(nextStatus.variation_percent);
      setSummary(period);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to load simulator status.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), isRunning ? 5000 : 15_000);
    return () => window.clearInterval(timer);
  }, [isRunning, load]);

  const saveScenario = async () => {
    setSaving(true);
    try {
      const nextStatus = await simulationApi.configure({
        base_load_kw: baseLoadKw,
        variation_percent: variationPercent,
      });
      setStatus(nextStatus);
      toast.success('Deterministic household profile saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save the demo scenario.');
    } finally {
      setSaving(false);
    }
  };

  const changeState = async (action: 'start' | 'stop' | 'reset') => {
    if (action === 'reset' && !window.confirm(
      'Reset all simulator data and regenerate a clean 30-day seeded history? CSV and push-meter readings will be preserved, and the live feed will stop.',
    )) return;

    setChangingState(action);
    try {
      const nextStatus = action === 'start'
        ? await simulationApi.start()
        : action === 'stop'
          ? await simulationApi.stop()
          : await simulationApi.reset();
      setStatus(nextStatus);
      await load();
      if (action === 'start') {
        toast.success(nextStatus.history_action === 'bootstrapped_empty_meter'
          ? 'Demo started with 30 days of seeded history.'
          : 'Demo readings started. Existing history was preserved.');
      } else if (action === 'stop') {
        toast.success('Demo feed stopped. This interval will not be backfilled.');
      } else {
        toast.success('Simulator-only data was reset and regenerated. Real and imported readings were preserved.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : `Unable to ${action} the simulator.`);
    } finally {
      setChangingState(null);
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="border-b border-white/10 pb-5">
          <div className="flex flex-wrap items-center gap-2">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-amber-300"><TestTube2 className="h-3.5 w-3.5" />Explicit demo source</p>
            <Badge className="border-amber-300/20 bg-amber-400/10 text-amber-200" variant="outline">Synthetic, never measured</Badge>
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-white">Demo simulator</h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">A reproducible household scenario with weekday and weekend routines, morning and evening peaks, and seeded variation. Every generated reading is stored as simulation data and is never presented as a real meter measurement.</p>
        </header>

        <section className="grid gap-3 md:grid-cols-3" aria-label="Persistent demo history status">
          <div className="rounded-xl border border-cyan-400/15 bg-gradient-to-br from-cyan-400/10 to-[#111827] p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-cyan-200"><History className="h-4 w-4" />Persisted context</div>
            <p className="mt-3 text-xl font-semibold text-white">{loading ? 'Checking…' : `${Math.round(status?.history_span_hours ?? 0)} hours`}</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">{status?.history_points ? `${status.history_points.toLocaleString()} labelled readings from ${compactDate(status.history_start_at)}.` : 'The first start prepares history when the meter is empty.'}</p>
          </div>
          <div className="rounded-xl border border-violet-400/15 bg-gradient-to-br from-violet-400/10 to-[#111827] p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-violet-200"><ShieldCheck className="h-4 w-4" />Forecast foundation</div>
            <p className="mt-3 text-xl font-semibold text-white">{status?.history_ready_for_forecast ? 'History available' : 'Building context'}</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">The demo targets {status?.bootstrap_days ?? 30} days at {status?.bootstrap_interval_minutes ?? 15}-minute intervals, exceeding the {status?.minimum_forecast_history_hours ?? 336}-hour forecast lookback.</p>
          </div>
          <div className="rounded-xl border border-emerald-400/15 bg-gradient-to-br from-emerald-400/10 to-[#111827] p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-200"><Clock3 className="h-4 w-4" />Wake continuity</div>
            <p className="mt-3 text-xl font-semibold text-white">{status?.last_catch_up_at ? `${status.last_catch_up_points} restored` : 'Ready for the next wake'}</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">{status?.last_catch_up_at ? `Last catch-up ${compactDate(status.last_catch_up_at)} at ${status.last_catch_up_interval_minutes}-minute cadence.` : 'If Azure sleeps while this feed is running, only the forward outage interval will be generated.'}</p>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <Card className="rounded-lg border-white/10 bg-[#111827]">
            <CardHeader><CardTitle className="flex items-center justify-between text-sm"><span>Feed state</span><span className={isRunning ? 'text-emerald-300' : 'text-slate-400'}>{loading ? 'Checking' : isRunning ? 'Running' : 'Stopped'}</span></CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div><p className="text-xs text-slate-500">Session uptime</p><p className="mt-1 font-mono text-2xl text-white">{durationLabel(status?.uptime ?? 0)}</p></div>
              <div className="grid grid-cols-2 gap-2">
                <Button aria-label="Start demo" disabled={loading || isRunning || changingState !== null} onClick={() => changeState('start')} title="Start"><Play />{changingState === 'start' ? 'Preparing…' : 'Start'}</Button>
                <Button aria-label="Stop demo" disabled={loading || !isRunning || changingState !== null} onClick={() => changeState('stop')} title="Stop" variant="destructive"><Square />Stop</Button>
              </div>
              <Button className="w-full border-amber-300/20 text-amber-200 hover:bg-amber-400/10" disabled={loading || changingState !== null} onClick={() => changeState('reset')} variant="outline"><RotateCcw />{changingState === 'reset' ? 'Regenerating…' : 'Reset demo data'}</Button>
              <div className="space-y-2 text-xs leading-5 text-slate-500">
                <p>Starting makes the simulator the active writer. Push API writes are blocked until it stops.</p>
                <p>Stopping is intentional: that time remains a visible gap when you start again.</p>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-lg border-white/10 bg-[#111827]">
            <CardHeader><CardTitle className="text-sm">Household profile</CardTitle><p className="text-xs leading-5 text-slate-400">Tune the scale and variation while keeping the same reproducible daily behavior. The same seed and timestamp always produce the same reading.</p></CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="grid gap-2 text-xs text-slate-400"><span className="flex justify-between"><span>Base load</span><span className="text-white">{baseLoadKw.toFixed(1)} kW</span></span><input className="accent-cyan-400" max="20" min="0.1" onChange={(event) => setBaseLoadKw(Number(event.target.value))} step="0.1" type="range" value={baseLoadKw} /></label>
                <label className="grid gap-2 text-xs text-slate-400"><span className="flex justify-between"><span>Seeded variation</span><span className="text-white">{variationPercent}%</span></span><input className="accent-cyan-400" max="50" min="0" onChange={(event) => setVariationPercent(Number(event.target.value))} step="1" type="range" value={variationPercent} /></label>
              </div>
              <div className="grid gap-3 rounded-lg border border-white/10 bg-slate-950/40 p-4 text-xs leading-5 text-slate-400 sm:grid-cols-2">
                <p><span className="font-medium text-white">Weekdays:</span> earlier morning activity, quieter daytime demand, and a stronger evening peak.</p>
                <p><span className="font-medium text-white">Weekends:</span> later morning activity and broader daytime household use.</p>
              </div>
              <Button disabled={saving} onClick={saveScenario}><Save />{saving ? 'Saving…' : 'Save household profile'}</Button>
            </CardContent>
          </Card>
        </section>

        <Card className="rounded-lg border-white/10 bg-[#111827]">
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><Activity className="h-4 w-4 text-emerald-400" />Last 15 minutes</CardTitle><p className="text-xs text-slate-400">This chart uses persisted readings; the source and simulated quality label remain available in monitoring and raw-data views.</p></CardHeader>
          <CardContent>{summary && summary.points.length ? <ConsumptionChart summary={summary} variant="compact" /> : <div className="flex h-80 items-center justify-center text-sm text-slate-400"><Database className="mr-2 h-4 w-4" />Start the simulator to generate the first demo reading.</div>}</CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
