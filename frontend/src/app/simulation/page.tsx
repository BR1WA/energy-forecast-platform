'use client';

import { useCallback, useEffect, useState } from 'react';
import { Activity, Play, RotateCcw, Save, Square, TestTube2 } from 'lucide-react';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { ConsumptionChart } from '@/components/consumption/consumption-chart';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { consumptionApi, simulationApi } from '@/lib/api';
import type { ConsumptionPeriodSummary } from '@/types';

function durationLabel(seconds: number) {
  const hours = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const minutes = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const remainder = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${hours}:${minutes}:${remainder}`;
}

export default function SimulationPage() {
  const [isRunning, setIsRunning] = useState(false);
  const [uptime, setUptime] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [summary, setSummary] = useState<ConsumptionPeriodSummary | null>(null);
  const [baseLoadKw, setBaseLoadKw] = useState(1.2);
  const [variationPercent, setVariationPercent] = useState(10);

  const load = useCallback(async () => {
    try {
      const [status, period] = await Promise.all([
        simulationApi.getStatus(),
        consumptionApi.getPeriod('live'),
      ]);
      setIsRunning(status.is_running);
      setUptime(status.uptime || 0);
      if (status.base_load_kw !== undefined) setBaseLoadKw(status.base_load_kw);
      if (status.variation_percent !== undefined) setVariationPercent(status.variation_percent);
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
      await simulationApi.configure({
        base_load_kw: baseLoadKw,
        variation_percent: variationPercent,
      });
      toast.success('Demo load profile saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save the demo scenario.');
    } finally {
      setSaving(false);
    }
  };

  const changeState = async (action: 'start' | 'stop' | 'reset') => {
    try {
      if (action === 'start') await simulationApi.start();
      if (action === 'stop') await simulationApi.stop();
      if (action === 'reset') await simulationApi.reset();
      await load();
      toast.success(action === 'start' ? 'Demo readings started.' : action === 'stop' ? 'Demo readings stopped.' : 'Demo scenario reset.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : `Unable to ${action} the simulator.`);
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="border-b border-white/10 pb-5">
          <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase text-amber-300"><TestTube2 className="h-3.5 w-3.5" />Explicit demo source</p>
          <h1 className="text-2xl font-semibold text-white">Demo simulator</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">Generate clearly labelled synthetic household readings for demonstrations. These readings are not measurements from a real meter.</p>
        </header>

        <section className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <Card className="rounded-lg border-white/10 bg-[#111827]">
            <CardHeader><CardTitle className="flex items-center justify-between text-sm"><span>Feed state</span><span className={isRunning ? 'text-emerald-300' : 'text-slate-400'}>{loading ? 'Checking' : isRunning ? 'Running' : 'Stopped'}</span></CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div><p className="text-xs text-slate-500">Session uptime</p><p className="mt-1 font-mono text-2xl text-white">{durationLabel(uptime)}</p></div>
              <div className="grid grid-cols-3 gap-2">
                <Button aria-label="Start demo" disabled={loading || isRunning} onClick={() => changeState('start')} title="Start"><Play /></Button>
                <Button aria-label="Stop demo" disabled={loading || !isRunning} onClick={() => changeState('stop')} title="Stop" variant="destructive"><Square /></Button>
                <Button aria-label="Reset scenario" disabled={loading} onClick={() => changeState('reset')} title="Reset scenario" variant="outline"><RotateCcw /></Button>
              </div>
              <p className="text-xs text-slate-500">Starting this feed makes the simulator the active writer. Push API writes are blocked until the simulator is stopped.</p>
            </CardContent>
          </Card>

          <Card className="rounded-lg border-white/10 bg-[#111827]">
            <CardHeader><CardTitle className="text-sm">Load profile</CardTitle><p className="text-xs text-slate-400">Configure a generic synthetic load without appliance or generation assumptions.</p></CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="grid gap-2 text-xs text-slate-400"><span className="flex justify-between"><span>Base load</span><span className="text-white">{baseLoadKw.toFixed(1)} kW</span></span><input className="accent-cyan-400" max="20" min="0.1" onChange={(event) => setBaseLoadKw(Number(event.target.value))} step="0.1" type="range" value={baseLoadKw} /></label>
                <label className="grid gap-2 text-xs text-slate-400"><span className="flex justify-between"><span>Random variation</span><span className="text-white">{variationPercent}%</span></span><input className="accent-cyan-400" max="50" min="0" onChange={(event) => setVariationPercent(Number(event.target.value))} step="1" type="range" value={variationPercent} /></label>
              </div>
              <Button disabled={saving} onClick={saveScenario}><Save />{saving ? 'Saving...' : 'Save load profile'}</Button>
            </CardContent>
          </Card>
        </section>

        <Card className="rounded-lg border-white/10 bg-[#111827]">
          <CardHeader><CardTitle className="flex items-center gap-2 text-sm"><Activity className="h-4 w-4 text-emerald-400" />Last 15 minutes</CardTitle><p className="text-xs text-slate-400">Every point remains labelled by its real source in the monitoring APIs.</p></CardHeader>
          <CardContent>{summary && summary.points.length ? <ConsumptionChart summary={summary} variant="compact" /> : <div className="flex h-80 items-center justify-center text-sm text-slate-400">Start the simulator to generate the first demo reading.</div>}</CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
