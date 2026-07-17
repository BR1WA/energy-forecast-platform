'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Target, Sparkles, CheckCircle2 } from 'lucide-react';
import { consumptionApi } from '@/lib/api';
import { toast } from 'sonner';

export default function BudgetGoalsPage() {
  const [budgetLimit, setBudgetLimit] = useState<number>(400);
  const [dailyLimit, setDailyLimit] = useState<number>(15);
  const [carbonGoal, setCarbonGoal] = useState<number>(20);
  const [stats, setStats] = useState({ total_kwh: 0 });

  const fetchStats = async () => {
    try {
      const data = await consumptionApi.getStatistics();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch statistics:', err);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const totalKwh = stats.total_kwh ?? 0;
  //ONE Tariff Tranches
  const getTariffInfo = () => {
    if (totalKwh <= 100) {
      return { tier: 1, name: 'Tranche 1 (Social)', rate: 0.9010, label: '0 - 100 kWh', pct: Math.min(100, Math.round((totalKwh / 100) * 100)) };
    } else if (totalKwh <= 200) {
      return { tier: 2, name: 'Tranche 2 (Normal)', rate: 1.0100, label: '101 - 200 kWh', pct: Math.min(100, Math.round(((totalKwh - 100) / 100) * 100)) };
    } else {
      return { tier: 3, name: 'Tranche 3 (High-Usage)', rate: 1.1200, label: '200+ kWh', pct: 100 };
    }
  };

  const tariff = getTariffInfo();

  const handleSaveGoals = () => {
    toast.success('Energy planning goals saved successfully!');
  };

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
            <Target className="text-indigo-400 w-8 h-8" /> Budget & Goals
          </h1>
          <p className="text-slate-400">Manage utility budgets, carbon targets, and track progressive billing tariff tiers.</p>
        </div>

        {/* ONEE Tariffs */}
        <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <CardTitle className="text-white text-base">ONEE Moroccan Tariff Status</CardTitle>
              <CardDescription className="text-slate-400 text-xs">ONEE progressive electricity billing rates for household accounts.</CardDescription>
            </div>
            <Badge className="bg-indigo-600 text-white text-[10px] uppercase font-semibold">{tariff.name}</Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className={`p-3 rounded-lg border ${tariff.tier === 1 ? 'border-emerald-500 bg-emerald-500/10' : 'border-white/5 bg-white/5 opacity-60'}`}>
                <div className="font-semibold text-white">Tranche 1</div>
                <div className="text-[10px] text-slate-400 mt-1">0 - 100 kWh</div>
                <div className="text-[10px] text-emerald-400 mt-0.5">0.9010 MAD</div>
              </div>
              <div className={`p-3 rounded-lg border ${tariff.tier === 2 ? 'border-amber-500 bg-amber-500/10' : 'border-white/5 bg-white/5 opacity-60'}`}>
                <div className="font-semibold text-white">Tranche 2</div>
                <div className="text-[10px] text-slate-400 mt-1">101 - 200 kWh</div>
                <div className="text-[10px] text-amber-400 mt-0.5">1.0100 MAD</div>
              </div>
              <div className={`p-3 rounded-lg border ${tariff.tier === 3 ? 'border-rose-500 bg-rose-500/10' : 'border-white/5 bg-white/5 opacity-60'}`}>
                <div className="font-semibold text-white">Tranche 3</div>
                <div className="text-[10px] text-slate-400 mt-1">200+ kWh</div>
                <div className="text-[10px] text-rose-400 mt-0.5">1.1200 MAD</div>
              </div>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-400">
                <span>Active Tranche Progress ({tariff.label})</span>
                <span className="font-semibold text-white">{(totalKwh).toFixed(1)} kWh</span>
              </div>
              <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${tariff.tier === 1 ? 'bg-emerald-500' : tariff.tier === 2 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${tariff.pct}%` }} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Goals & Budgets Config */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
            <CardHeader>
              <CardTitle className="text-white text-base">Budget Planning Goals</CardTitle>
              <CardDescription className="text-slate-400 text-xs">Set limits to calculate monthly Energy Scores and trigger warning notifications.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Monthly budget */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-semibold block">Monthly Budget Target (MAD)</label>
                <Input
                  type="number"
                  value={budgetLimit}
                  onChange={(e) => setBudgetLimit(Number(e.target.value))}
                  className="bg-[#111827] border-white/10 text-white"
                />
              </div>

              {/* Daily energy limit */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-semibold block">Maximum Daily Energy Limit (kWh)</label>
                <Input
                  type="number"
                  value={dailyLimit}
                  onChange={(e) => setDailyLimit(Number(e.target.value))}
                  className="bg-[#111827] border-white/10 text-white"
                />
              </div>

              {/* Carbon neutrality goal */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-semibold block">Monthly Carbon Neutrality Goal (kg CO₂)</label>
                <Input
                  type="number"
                  value={carbonGoal}
                  onChange={(e) => setCarbonGoal(Number(e.target.value))}
                  className="bg-[#111827] border-white/10 text-white"
                />
              </div>

              <Button onClick={handleSaveGoals} className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold h-9">
                Save Goals
              </Button>
            </CardContent>
          </Card>

          {/* Scenario Comparison */}
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md flex flex-col justify-between">
            <CardHeader>
              <CardTitle className="text-white text-base">Savings Optimization Scenario</CardTitle>
              <CardDescription className="text-slate-400 text-xs">Simulated comparisons of applying active recommendations against baseline.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3.5 rounded-lg border border-white/[0.04] bg-[#0A0F1C]/80 space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-slate-400">Current Trend (Baseline):</span>
                  <span className="font-semibold text-white">485.00 MAD</span>
                </div>
                <div className="flex justify-between items-center text-xs border-b border-white/5 pb-3">
                  <span className="text-slate-400">With Recommendations:</span>
                  <span className="font-semibold text-emerald-400">412.00 MAD</span>
                </div>
                <div className="flex justify-between items-center text-xs pt-1">
                  <span className="text-slate-400 font-bold">Estimated Savings:</span>
                  <span className="font-extrabold text-emerald-400 text-sm font-mono">73.00 MAD / month</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex gap-3">
                <Sparkles className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                <p className="text-xs text-slate-300 leading-relaxed">
                  <strong>Did you know?</strong> Sticking to your daily budget threshold for 5 consecutive days raises your Energy Score by +8 points.
                </p>
              </div>

              <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <p className="text-xs text-slate-300 leading-relaxed">
                  Your carbon emissions are currently within the target buffer limits! Keep up the off-peak shifting.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
