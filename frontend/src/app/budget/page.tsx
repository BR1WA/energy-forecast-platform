'use client';

import React, { useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Target, TrendingUp, Wallet } from 'lucide-react';
import { consumptionApi, settingsApi } from '@/lib/api';
import { toast } from 'sonner';

type MonthlySummary = Awaited<ReturnType<typeof consumptionApi.getStatistics>>;

export default function BudgetGoalsPage() {
  const [summary, setSummary] = useState<MonthlySummary | null>(null);
  const [budget, setBudget] = useState('');
  const [saving, setSaving] = useState(false);

  const refresh = async () => {
    try {
      const [monthly, savedBudget] = await Promise.all([consumptionApi.getStatistics(), settingsApi.getBudget()]);
      setSummary(monthly);
      setBudget(savedBudget?.monthly_budget_mad ? String(savedBudget.monthly_budget_mad) : '');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to load budget progress.');
    }
  };

  useEffect(() => { refresh(); }, []);

  const saveBudget = async () => {
    const value = Number(budget);
    if (!Number.isFinite(value) || value <= 0) {
      toast.error('Enter a monthly budget greater than zero.');
      return;
    }
    setSaving(true);
    try {
      await settingsApi.setBudget({ monthly_budget_mad: value });
      toast.success('Monthly budget saved.');
      await refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save budget.');
    } finally {
      setSaving(false);
    }
  };

  const tariff = summary?.tariff;
  const budgetInfo = summary?.budget;
  const progress = Math.min(100, budgetInfo?.progress_pct ?? 0);

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Target className="h-6 w-6 text-indigo-400" />Budget & Progress</h1>
          <p className="mt-1 text-sm text-slate-400">Track actual interval-based energy costs for this month and compare them with the last one.</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="border-white/10 bg-[#111827]/80 lg:col-span-2">
            <CardHeader><CardTitle>Monthly budget</CardTitle><CardDescription>This budget is saved for your site and is independent of alert thresholds.</CardDescription></CardHeader>
            <CardContent className="space-y-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="flex-1 space-y-2"><label className="text-sm text-slate-300">Budget ({tariff?.currency || 'MAD'})</label><Input type="number" min="0" value={budget} onChange={(event) => setBudget(event.target.value)} /></div>
                <Button onClick={saveBudget} disabled={saving}>{saving ? 'Saving...' : 'Save budget'}</Button>
              </div>
              <div className="space-y-2"><div className="flex justify-between text-sm text-slate-300"><span>Spent this month</span><span>{tariff?.currency || 'MAD'} {(budgetInfo?.spent_mad ?? 0).toFixed(2)} {budgetInfo?.target_mad ? `/ ${(budgetInfo.target_mad).toFixed(2)}` : ''}</span></div><div className="h-2 overflow-hidden rounded bg-white/10"><div className={progress >= 100 ? 'h-full bg-rose-500' : 'h-full bg-indigo-500'} style={{ width: `${progress}%` }} /></div><p className="text-xs text-slate-500">{budgetInfo?.target_mad ? `${progress.toFixed(1)}% used. Projected month-end cost: ${tariff?.currency || 'MAD'} ${(budgetInfo.projected_mad).toFixed(2)}.` : 'Set a budget to see progress and projected overrun.'}</p></div>
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-[#111827]/80"><CardHeader><CardTitle className="flex items-center gap-2"><TrendingUp className="h-4 w-4 text-cyan-400" />Month comparison</CardTitle></CardHeader><CardContent className="space-y-2"><div className="text-3xl font-bold text-white">{summary?.comparison_pct === null || summary?.comparison_pct === undefined ? 'N/A' : `${summary.comparison_pct > 0 ? '+' : ''}${summary.comparison_pct}%`}</div><p className="text-sm text-slate-400">This month: {(summary?.total_kwh ?? 0).toFixed(2)} kWh</p><p className="text-sm text-slate-400">Last month: {(summary?.previous_month.total_kwh ?? 0).toFixed(2)} kWh</p><p className="text-xs text-slate-500">Coverage: {(summary?.coverage_pct ?? 0).toFixed(1)}%</p></CardContent></Card>
        </div>

        <Card className="border-white/10 bg-[#111827]/80"><CardHeader><CardTitle className="flex items-center gap-2"><Wallet className="h-4 w-4 text-emerald-400" />Site tariff</CardTitle><CardDescription>Rates are applied to each timestamp interval in the site timezone.</CardDescription></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2"><div className="border border-amber-500/30 bg-amber-500/10 p-4"><div className="text-sm font-medium text-white">Peak hours</div><div className="mt-1 text-2xl font-bold text-amber-300">{tariff?.peak_rate.toFixed(4) ?? '0.0000'} {tariff?.currency || 'MAD'}</div><p className="mt-1 text-xs text-slate-400">{tariff?.peak_start_hour ?? 0}:00 to {tariff?.peak_end_hour ?? 0}:00</p></div><div className="border border-emerald-500/30 bg-emerald-500/10 p-4"><div className="text-sm font-medium text-white">Off-peak hours</div><div className="mt-1 text-2xl font-bold text-emerald-300">{tariff?.off_peak_rate.toFixed(4) ?? '0.0000'} {tariff?.currency || 'MAD'}</div><p className="mt-1 text-xs text-slate-400">All remaining hours</p></div></CardContent></Card>
      </div>
    </AppLayout>
  );
}
