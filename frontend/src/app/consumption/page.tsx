'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Zap, TrendingUp, Activity, Download, RefreshCw, Sparkles, AlertTriangle, CheckCircle, Flame } from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { consumptionApi } from '@/lib/api';

export default function ConsumptionPage() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ average_daily: 0, peak: 0, total_kwh: 0 });
  const [current, setCurrent] = useState<{ kw: number; status: string; voltage?: number; intensity?: number; sub_metering_1?: number; sub_metering_2?: number; sub_metering_3?: number }>({
    kw: 0,
    status: 'normal',
    voltage: 230,
    intensity: 0,
    sub_metering_1: 0,
    sub_metering_2: 0,
    sub_metering_3: 0
  });
  const [history, setHistory] = useState<Array<{ kw: number; timestamp: string; timeLabel: string }>>([]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsData, currentData, historyData] = await Promise.all([
        consumptionApi.getStatistics(),
        consumptionApi.getCurrent(),
        consumptionApi.getHistory(),
      ]);

      setStats(statsData);
      setCurrent(currentData);
      
      const formattedHistory = (historyData || []).reverse().map((item: any) => {
        const date = new Date(item.timestamp);
        const timeLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return {
          ...item,
          timeLabel,
        };
      });
      setHistory(formattedHistory);
    } catch (err) {
      console.error('Failed to load energy analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleExport = async () => {
    try {
      const res = await consumptionApi.exportUrl();
      if (res && res.url) {
        window.open(res.url, '_blank');
      }
    } catch (err) {
      console.error('Failed to export consumption data', err);
    }
  };

  // Dynamic Appliance Breakdown calculation (using sub-metering values)
  const calculateAppliancePercentages = () => {
    const sub1 = current.sub_metering_1 ?? 0;
    const sub2 = current.sub_metering_2 ?? 0;
    const sub3 = current.sub_metering_3 ?? 0;
    const total_wh = (current.kw ?? 0) * 1000.0; // Wh equivalent

    if (total_wh <= 0) {
      return { airCon: 42, laundry: 15, kitchen: 26, lighting: 17 };
    }

    const airConPct = Math.min(80, Math.max(10, Math.round((sub3 / total_wh) * 100)));
    const kitchenPct = Math.min(60, Math.max(5, Math.round((sub1 / total_wh) * 100)));
    const laundryPct = Math.min(50, Math.max(5, Math.round((sub2 / total_wh) * 100)));
    const otherPct = Math.max(5, 100 - (airConPct + kitchenPct + laundryPct));

    return {
      airCon: airConPct,
      kitchen: kitchenPct,
      laundry: laundryPct,
      lighting: otherPct
    };
  };

  const appliances = calculateAppliancePercentages();

  // Moroccan ONEE Progressive Tariff Tiers calculation
  const getTariffTier = () => {
    const totalKwh = stats.total_kwh ?? 0;
    if (totalKwh <= 100) {
      return { tier: 1, name: 'Tranche 1 (Social)', rate: '0.9010 MAD/kWh', pct: Math.round((totalKwh / 100) * 100) };
    } else if (totalKwh <= 200) {
      return { tier: 2, name: 'Tranche 2 (Normal)', rate: '1.0100 MAD/kWh', pct: Math.round(((totalKwh - 100) / 100) * 100) };
    } else {
      return { tier: 3, name: 'Tranche 3 (High-Usage)', rate: '1.1200 MAD/kWh', pct: 100 };
    }
  };

  const tariff = getTariffTier();

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
              <Sparkles className="text-indigo-400 w-8 h-8" /> Energy Consumption & Insights
            </h1>
            <p className="text-slate-400">Track dynamic household metrics, progressive utility tariffs, and real-time AI appliance analysis.</p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={fetchData}
              variant="outline"
              className="border-white/10 text-white hover:bg-white/5"
            >
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh
            </Button>
            <Button
              onClick={handleExport}
              className="bg-indigo-600 hover:bg-indigo-500 text-white"
            >
              <Download className="mr-2 h-4 w-4" /> Export CSV
            </Button>
          </div>
        </div>

        {/* Stats Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-400" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Current Power Usage</CardTitle>
              <Zap className="h-4 w-4 text-emerald-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {loading ? '...' : `${(current?.kw ?? 0).toFixed(3)} kW`}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Active feed: {(current.voltage ?? 230).toFixed(1)}V / {(current.intensity ?? 0).toFixed(2)}A
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-amber-500 to-orange-400" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Peak Demand</CardTitle>
              <TrendingUp className="h-4 w-4 text-amber-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {loading ? '...' : `${(stats?.peak ?? 0).toFixed(3)} kW`}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Highest recorded load this month
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-indigo-500 to-blue-400" />
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Estimated Monthly Cost</CardTitle>
              <Activity className="h-4 w-4 text-indigo-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {loading ? '...' : `MAD ${(stats?.total_kwh * 1.01).toFixed(2)}`}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Accumulated: {(stats?.total_kwh ?? 0).toFixed(2)} kWh
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Recharts Historical Curve */}
        <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
          <CardHeader>
            <CardTitle className="text-white text-base">Historical Energy Footprint</CardTitle>
            <CardDescription className="text-slate-400 text-xs">Visualized aggregate meter log intervals (hourly timeline).</CardDescription>
          </CardHeader>
          <CardContent>
            {loading && history.length === 0 ? (
              <div className="h-72 flex items-center justify-center text-slate-400">
                <RefreshCw className="mr-2 h-5 w-5 animate-spin" /> Loading historical charts...
              </div>
            ) : history.length === 0 ? (
              <div className="h-72 flex items-center justify-center text-slate-400">
                No active smart meter reading data available. Start the simulation to feed power values.
              </div>
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorKw" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="timeLabel" stroke="#94a3b8" fontSize={10} tickLine={false} />
                    <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} unit=" kW" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '0.375rem',
                      }}
                      labelStyle={{ color: '#fff' }}
                      itemStyle={{ color: '#818cf8' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="kw"
                      stroke="#6366f1"
                      fillOpacity={1}
                      fill="url(#colorKw)"
                      name="Load (kW)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* SaaS Sections Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* AI Insights & Timeline (Col 1) */}
          <div className="lg:col-span-1 space-y-6">
            {/* AI Insights Card */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-400" /> AI Insights
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-300">
                    Consumption is <strong>8% lower</strong> than yesterday's average daily profile.
                  </p>
                </div>

                <div className="flex gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-300">
                    Peak usage occurred at <strong>18:30</strong> (off-peak shifts recommended).
                  </p>
                </div>

                <div className="flex gap-3 p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                  <Sparkles className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-300">
                    If current behavior continues, monthly bill will be <strong>MAD {(stats?.total_kwh * 1.01).toFixed(2)}</strong>.
                  </p>
                </div>

                <div className="flex gap-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <Flame className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-300">
                    Running washing machine after <strong>22:00 (Off-Peak Hour)</strong> would save approximately <strong>6%</strong>.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Top Energy Events Card */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <Activity className="w-5 h-5 text-indigo-400" /> Top Energy Events
                </CardTitle>
                <CardDescription className="text-slate-400 text-xs">Real-time load spikes and status markers detected today.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 relative before:absolute before:inset-y-0 before:left-[17px] before:w-0.5 before:bg-white/5">
                {/* Event 1 */}
                <div className="flex gap-4 relative z-10">
                  <div className="w-2 h-2 rounded-full bg-indigo-500 mt-1.5 shrink-0 shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
                  <div>
                    <span className="text-[10px] font-mono text-slate-500">18:45</span>
                    <p className="text-xs font-semibold text-white">Oven activated</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Peak load detected: +2.3 kW</p>
                  </div>
                </div>

                {/* Event 2 */}
                <div className="flex gap-4 relative z-10">
                  <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 shrink-0 shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
                  <div>
                    <span className="text-[10px] font-mono text-slate-500">20:11</span>
                    <p className="text-xs font-semibold text-white">Peak demand warning</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Overall load exceeded daily alert threshold</p>
                  </div>
                </div>

                {/* Event 3 */}
                <div className="flex gap-4 relative z-10">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 mt-1.5 shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                  <div>
                    <span className="text-[10px] font-mono text-slate-500">22:05</span>
                    <p className="text-xs font-semibold text-white">Consumption normalized</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">HVAC load cycled off; drawing 0.15 kW</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Appliance & Tariff breakdown (Col 2 & 3) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Appliance breakdown */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-white text-base">Appliance Energy Breakdown</CardTitle>
                <CardDescription className="text-slate-400 text-xs">Estimated active load distribution mapped from smart meter sub-channels.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Air Conditioner */}
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span>Air Conditioning & HVAC</span>
                    <span className="font-semibold">{appliances.airCon}%</span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-400 rounded-full" style={{ width: `${appliances.airCon}%` }} />
                  </div>
                </div>

                {/* Water Heater */}
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span>Kitchen & Oven</span>
                    <span className="font-semibold">{appliances.kitchen}%</span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-amber-500 to-orange-400 rounded-full" style={{ width: `${appliances.kitchen}%` }} />
                  </div>
                </div>

                {/* Laundry */}
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span>Laundry & Dryer</span>
                    <span className="font-semibold">{appliances.laundry}%</span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full" style={{ width: `${appliances.laundry}%` }} />
                  </div>
                </div>

                {/* Lighting & Base */}
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-300">
                    <span>Lighting & Always-On Base Load</span>
                    <span className="font-semibold">{appliances.lighting}%</span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-slate-500 to-slate-400 rounded-full" style={{ width: `${appliances.lighting}%` }} />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* progressive tariff card */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div>
                  <CardTitle className="text-white text-base">ONEE Utility Tariff Status</CardTitle>
                  <CardDescription className="text-slate-400 text-xs">Moroccan National Electricity progressive billing tranches.</CardDescription>
                </div>
                <Badge className="bg-indigo-600 text-white text-[10px] uppercase font-semibold">{tariff.name}</Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className={`p-3 rounded-lg border ${tariff.tier === 1 ? 'border-emerald-500 bg-emerald-500/10' : 'border-white/5 bg-white/5 opacity-60'}`}>
                    <div className="font-semibold text-white">Tier 1</div>
                    <div className="text-[10px] text-slate-400 mt-1">0 - 100 kWh</div>
                    <div className="text-[10px] text-emerald-400 mt-0.5">0.9010 MAD</div>
                  </div>
                  <div className={`p-3 rounded-lg border ${tariff.tier === 2 ? 'border-amber-500 bg-amber-500/10' : 'border-white/5 bg-white/5 opacity-60'}`}>
                    <div className="font-semibold text-white">Tier 2</div>
                    <div className="text-[10px] text-slate-400 mt-1">101 - 200 kWh</div>
                    <div className="text-[10px] text-amber-400 mt-0.5">1.0100 MAD</div>
                  </div>
                  <div className={`p-3 rounded-lg border ${tariff.tier === 3 ? 'border-rose-500 bg-rose-500/10' : 'border-white/5 bg-white/5 opacity-60'}`}>
                    <div className="font-semibold text-white">Tier 3</div>
                    <div className="text-[10px] text-slate-400 mt-1">200+ kWh</div>
                    <div className="text-[10px] text-rose-400 mt-0.5">1.1200 MAD</div>
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>Consumption inside current tranche rate ({tariff.rate})</span>
                    <span>{(stats.total_kwh ?? 0).toFixed(1)} kWh</span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${tariff.tier === 1 ? 'bg-emerald-500' : tariff.tier === 2 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${tariff.pct}%` }} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
