'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { toast } from 'sonner';
import {
  BarChart3,
  TrendingUp,
  Activity,
  Calendar,
  FileText,
  Lock,
  Loader2,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
} from 'recharts';
import { analyticsApi } from '@/lib/api';

interface AnalyticsData {
  total_forecasts: number;
  total_alerts: number;
  unacknowledged_alerts: number;
  avg_peak_power: number | null;
  weekly_consumption?: Array<{
    week: string;
    actual: number;
    predicted: number;
    savings: number;
  }>;
  consumption_by_hour?: Array<{
    hour: string;
    weekday: number;
    weekend: number;
  }>;
  heatmap_data?: Array<{
    day: string;
    hour: number;
    value: number;
  }>;
}

// Seeded pseudo-random number generator for deterministic demo data
function seededRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

const consumptionByHour = Array.from({ length: 24 }, (_, i) => ({
  hour: `${String(i).padStart(2, '0')}:00`,
  weekday: Math.round(2000 + Math.sin((i - 6) * (Math.PI / 12)) * 2500 + (seededRandom(i * 3 + 1) - 0.5) * 300),
  weekend: Math.round(1500 + Math.sin((i - 8) * (Math.PI / 12)) * 1800 + (seededRandom(i * 3 + 2) - 0.5) * 200),
}));

const weeklyConsumption = [
  { week: 'W1', actual: 28500, predicted: 28200, savings: 300 },
  { week: 'W2', actual: 31200, predicted: 30800, savings: 400 },
  { week: 'W3', actual: 27800, predicted: 28100, savings: -300 },
  { week: 'W4', actual: 33500, predicted: 33000, savings: 500 },
  { week: 'W5', actual: 29600, predicted: 29400, savings: 200 },
  { week: 'W6', actual: 26200, predicted: 26800, savings: -600 },
  { week: 'W7', actual: 30100, predicted: 29800, savings: 300 },
  { week: 'W8', actual: 32400, predicted: 32100, savings: 300 },
];

const heatmapData = (() => {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const data: { day: string; hour: number; value: number }[] = [];
  let seedCounter = 0;
  days.forEach((day) => {
    for (let h = 0; h < 24; h++) {
      const isWeekend = day === 'Sat' || day === 'Sun';
      const base = isWeekend ? 1500 : 2000;
      const peak = isWeekend ? 1800 : 3000;
      const factor = Math.sin((h - (isWeekend ? 8 : 6)) * (Math.PI / 12));
      data.push({
        day,
        hour: h,
        value: Math.round(base + Math.max(0, factor) * (peak - base) + (seededRandom(seedCounter++) - 0.5) * 300),
      });
    }
  });
  return data;
})();

function getHeatColor(value: number): string {
  const min = 1200;
  const max = 5000;
  const ratio = Math.max(0, Math.min(1, (value - min) / (max - min)));
  if (ratio < 0.25) return 'bg-blue-900/40';
  if (ratio < 0.5) return 'bg-blue-700/40';
  if (ratio < 0.75) return 'bg-cyan-500/40';
  return 'bg-emerald-500/50';
}

export default function AnalyticsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('overview');
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [systemSettings, setSystemSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  const isFree = user?.subscription_tier === 'free';
  const isEnterprise = user?.subscription_tier === 'enterprise';

  const finalHeatmapData = analytics?.heatmap_data || heatmapData;

  useEffect(() => {
    analyticsApi
      .getSummary()
      .then((data) => setAnalytics(data as unknown as AnalyticsData))
      .catch(console.error)
      .finally(() => setLoading(false));

    // Fetch system settings for localization and currency
    fetch('http://localhost:8000/api/v1/settings')
      .then((res) => res.json())
      .then((data) => setSystemSettings(data))
      .catch(console.error);
  }, []);

  const handleDownloadPDF = async () => {
    if (user?.subscription_tier !== 'enterprise') {
      toast.warning('PDF Report Export is an Enterprise tier feature. Please upgrade your plan.');
      router.push('/plans');
      return;
    }

    setDownloading(true);
    try {
      const blob = await analyticsApi.downloadReportPDF();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `energy_report_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
      toast.error('Failed to download PDF report');
    } finally {
      setDownloading(false);
    }
  };

  const getMonthlyConsumption = () => {
    const data = analytics?.weekly_consumption || weeklyConsumption;
    const last4 = data.slice(-4);
    const sumWh = last4.reduce((sum, item) => sum + item.actual, 0);
    return sumWh / 1000; // Wh to kWh
  };

  const getBillingEstimate = (monthlyKWh: number) => {
    const peakRate = systemSettings?.peak_rate ?? 1.1;
    const offPeakRate = systemSettings?.off_peak_rate ?? 0.8;
    const blendedRate = (16 * peakRate + 8 * offPeakRate) / 24;
    return monthlyKWh * blendedRate;
  };

  const monthlyKWh = getMonthlyConsumption();
  const billingEstimate = getBillingEstimate(monthlyKWh);

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-blue-400" />
              Analytics
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Historical trends, billing estimates, and hourly consumption patterns
            </p>
          </div>
          <div>
            <Button
              onClick={handleDownloadPDF}
              disabled={downloading}
              className="bg-blue-600 hover:bg-blue-500 text-white flex items-center gap-2 shadow-lg shadow-blue-500/10"
            >
              {downloading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : !isEnterprise ? (
                <Lock className="w-4 h-4 text-blue-200" />
              ) : (
                <FileText className="w-4 h-4" />
              )}
              {downloading ? 'Generating...' : 'Export PDF Report'}
            </Button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            {
              label: 'Avg Peak Power',
              value: loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : (analytics?.avg_peak_power ? `${analytics.avg_peak_power.toFixed(2)} kW` : '—'),
              trend: 'Global Active Power',
              icon: Activity,
              positive: true,
            },
            {
              label: 'Monthly Consumption',
              value: loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : `${monthlyKWh.toFixed(1)} kWh`,
              trend: 'Last 30 days',
              icon: TrendingUp,
              positive: true,
            },
            {
              label: 'Active Alerts',
              value: loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : (analytics ? analytics.unacknowledged_alerts.toString() : '—'),
              trend: analytics ? `${analytics.total_alerts} total` : '—',
              icon: Activity,
              positive: false,
            },
            {
              label: 'Billing Estimate',
              value: loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : `${systemSettings?.currency || 'MAD'} ${billingEstimate.toFixed(2)}`,
              trend: 'Estimated bill',
              icon: FileText,
              positive: true,
            },
          ].map((stat) => (
            <Card
              key={stat.label}
              className="glass-card border-white/[0.06] stat-card"
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">
                      {stat.label}
                    </p>
                    <p className="text-lg font-bold text-white mt-1">
                      {stat.value}
                    </p>
                    <p
                      className={`text-xs mt-0.5 ${
                        stat.positive ? 'text-emerald-400' : 'text-amber-400'
                      }`}
                    >
                      {stat.trend}
                    </p>
                  </div>
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                    <stat.icon className="w-4 h-4 text-blue-400" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white/[0.04] border border-white/[0.06] p-1">
            <TabsTrigger
              id="analytics-tab-overview"
              value="overview"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400"
            >
              Overview
            </TabsTrigger>
            <TabsTrigger
              id="analytics-tab-heatmap"
              value="heatmap"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400 flex items-center gap-1.5"
            >
              {isFree && <Lock className="w-3.5 h-3.5 text-slate-500" />}
              Consumption Heatmap
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6 mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Weekly Consumption Bar Chart */}
              <Card className="glass-card border-white/[0.06]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-white flex items-center justify-between w-full">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-blue-400" />
                      Weekly Consumption vs Prediction
                    </div>
                    <Badge variant="outline" className={`text-[10px] ${analytics ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10' : 'text-amber-500 border-amber-500/20 bg-amber-500/10'}`}>{analytics ? 'Live Data' : 'Demo Data'}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={analytics?.weekly_consumption || weeklyConsumption}>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(59,130,246,0.06)"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="week"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748B', fontSize: 12 }}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748B', fontSize: 12 }}
                          width={50}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#111827',
                            border: '1px solid rgba(59,130,246,0.15)',
                            borderRadius: '12px',
                            color: '#E2E8F0',
                            fontSize: '13px',
                          }}
                        />
                        <Bar
                          dataKey="actual"
                          fill="#3B82F6"
                          radius={[4, 4, 0, 0]}
                          name="Actual (Wh)"
                        />
                        <Bar
                          dataKey="predicted"
                          fill="#06B6D4"
                          radius={[4, 4, 0, 0]}
                          name="Predicted (Wh)"
                          opacity={0.7}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Hourly Pattern */}
              <Card className="glass-card border-white/[0.06]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-white flex items-center justify-between w-full">
                    <div className="flex items-center gap-2">
                      <Activity className="w-4 h-4 text-cyan-400" />
                      Hourly Consumption Pattern
                    </div>
                    <Badge variant="outline" className={`text-[10px] ${analytics ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10' : 'text-amber-500 border-amber-500/20 bg-amber-500/10'}`}>{analytics ? 'Live Data' : 'Demo Data'}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={analytics?.consumption_by_hour || consumptionByHour}>
                        <defs>
                          <linearGradient
                            id="gradWeekday"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#3B82F6"
                              stopOpacity={0.2}
                            />
                            <stop
                              offset="100%"
                              stopColor="#3B82F6"
                              stopOpacity={0}
                            />
                          </linearGradient>
                          <linearGradient
                            id="gradWeekend"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#10B981"
                              stopOpacity={0.2}
                            />
                            <stop
                              offset="100%"
                              stopColor="#10B981"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(59,130,246,0.06)"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="hour"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748B', fontSize: 10 }}
                          interval={3}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748B', fontSize: 12 }}
                          width={45}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#111827',
                            border: '1px solid rgba(59,130,246,0.15)',
                            borderRadius: '12px',
                            color: '#E2E8F0',
                            fontSize: '13px',
                          }}
                        />
                        <Legend />
                        <Area
                          type="monotone"
                          dataKey="weekday"
                          stroke="#3B82F6"
                          strokeWidth={2}
                          fill="url(#gradWeekday)"
                          name="Weekday (Wh)"
                        />
                        <Area
                          type="monotone"
                          dataKey="weekend"
                          stroke="#10B981"
                          strokeWidth={2}
                          fill="url(#gradWeekend)"
                          name="Weekend (Wh)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Heatmap Tab */}
          <TabsContent value="heatmap" className="space-y-6 mt-6">
            {isFree ? (
              <Card className="glass-card border-white/[0.06] relative overflow-hidden h-[380px] flex items-center justify-center">
                <div className="absolute inset-0 bg-[#0A0F1C]/80 backdrop-blur-[6px] z-10 flex flex-col items-center justify-center p-6 text-center">
                  <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center mb-4">
                    <Lock className="w-6 h-6 text-blue-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Unlock Consumption Heatmap with Pro</h3>
                  <p className="text-sm text-slate-400 max-w-md mb-6">
                    Get hourly breakdowns across the week to discover peak usage hours, optimize your home&apos;s schedule, and save on your electricity bill.
                  </p>
                  <Button
                    onClick={() => router.push('/plans')}
                    className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 shadow-lg shadow-blue-500/20"
                  >
                    Upgrade to Pro Plan
                  </Button>
                </div>
                {/* Blurred mockup of heatmap underneath */}
                <div className="w-full opacity-20 filter blur-[2px] pointer-events-none p-6 select-none">
                  <div className="overflow-x-auto">
                    {/* Hour labels */}
                    <div className="flex mb-1">
                      <div className="w-12 shrink-0" />
                      {Array.from({ length: 24 }, (_, i) => (
                        <div key={i} className="flex-1 min-w-[28px] text-center text-[10px] text-slate-500">
                          {i % 3 === 0 ? `${String(i).padStart(2, '0')}` : ''}
                        </div>
                      ))}
                    </div>
                    {/* Rows */}
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
                      <div key={day} className="flex gap-[2px] mb-[2px]">
                        <div className="w-12 shrink-0 flex items-center text-xs text-slate-400 font-medium">
                          {day}
                        </div>
                        {Array.from({ length: 24 }).map((_, i) => (
                          <div
                            key={i}
                            className="flex-1 min-w-[28px] h-7 rounded-sm bg-blue-900/40"
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            ) : (
              <Card className="glass-card border-white/[0.06]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-white flex items-center justify-between w-full">
                    <span>Weekly Consumption Heatmap</span>
                    <Badge variant="outline" className={`text-[10px] ${analytics ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10' : 'text-amber-500 border-amber-500/20 bg-amber-500/10'}`}>{analytics ? 'Live Data' : 'Demo Data'}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    {/* Hour labels */}
                    <div className="flex mb-1">
                      <div className="w-12 shrink-0" />
                      {Array.from({ length: 24 }, (_, i) => (
                        <div
                          key={i}
                          className="flex-1 min-w-[28px] text-center text-[10px] text-slate-500"
                        >
                          {i % 3 === 0 ? `${String(i).padStart(2, '0')}` : ''}
                        </div>
                      ))}
                    </div>
                    {/* Rows */}
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(
                      (day) => (
                        <div key={day} className="flex gap-[2px] mb-[2px]">
                          <div className="w-12 shrink-0 flex items-center text-xs text-slate-400 font-medium">
                            {day}
                          </div>
                          {finalHeatmapData
                            .filter((d) => d.day === day)
                            .map((cell, i) => (
                              <div
                                key={i}
                                className={`flex-1 min-w-[28px] h-7 rounded-sm ${getHeatColor(
                                  cell.value
                                )} transition-all duration-200 hover:ring-1 hover:ring-white/20 cursor-pointer`}
                                title={`${cell.day} ${String(cell.hour).padStart(
                                  2,
                                  '0'
                                )}:00 — ${cell.value} Wh`}
                              />
                            ))}
                        </div>
                      )
                    )}
                    {/* Legend */}
                    <div className="flex items-center justify-end gap-2 mt-4">
                      <span className="text-xs text-slate-500">Low</span>
                      <div className="flex gap-[2px]">
                        <div className="w-5 h-3 rounded-sm bg-blue-900/40" />
                        <div className="w-5 h-3 rounded-sm bg-blue-700/40" />
                        <div className="w-5 h-3 rounded-sm bg-cyan-500/40" />
                        <div className="w-5 h-3 rounded-sm bg-emerald-500/50" />
                      </div>
                      <span className="text-xs text-slate-500">High</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
