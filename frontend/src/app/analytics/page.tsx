'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  BarChart3,
  TrendingUp,
  Activity,
  Target,
  Calendar,
  Layers,
  FileText,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
} from 'recharts';
import { analyticsApi } from '@/lib/api';
import { Loader2 } from 'lucide-react';

interface AnalyticsData {
  total_forecasts: number;
  total_alerts: number;
  unacknowledged_alerts: number;
  models_used: Record<string, number>;
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
  monthly_accuracy?: Array<{
    month: string;
    cnn_bilstm: number;
    sota_hybrid: number;
    patchtst: number;
  }>;
  model_performance?: Array<{
    metric: string;
    cnn_bilstm: number;
    sota_hybrid: number;
    patchtst: number;
  }>;
  heatmap_data?: Array<{
    day: string;
    hour: number;
    value: number;
  }>;
}

const monthlyAccuracy = [
  { month: 'Jul', cnn_bilstm: 0.651, sota_hybrid: 0.825, patchtst: 0.798 },
  { month: 'Aug', cnn_bilstm: 0.662, sota_hybrid: 0.831, patchtst: 0.802 },
  { month: 'Sep', cnn_bilstm: 0.674, sota_hybrid: 0.835, patchtst: 0.807 },
  { month: 'Oct', cnn_bilstm: 0.681, sota_hybrid: 0.838, patchtst: 0.811 },
  { month: 'Nov', cnn_bilstm: 0.687, sota_hybrid: 0.840, patchtst: 0.813 },
  { month: 'Dec', cnn_bilstm: 0.691, sota_hybrid: 0.841, patchtst: 0.814 },
];

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

const modelPerformance = [
  { metric: 'MAE', cnn_bilstm: 85, sota_hybrid: 80, patchtst: 90 },
  { metric: 'RMSE', cnn_bilstm: 82, sota_hybrid: 78, patchtst: 88 },
  { metric: 'MAPE', cnn_bilstm: 88, sota_hybrid: 84, patchtst: 92 },
  { metric: 'R² Score', cnn_bilstm: 90, sota_hybrid: 87, patchtst: 94 },
  { metric: 'Speed', cnn_bilstm: 75, sota_hybrid: 70, patchtst: 85 },
  { metric: 'Stability', cnn_bilstm: 87, sota_hybrid: 83, patchtst: 91 },
];

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const finalHeatmapData = analytics?.heatmap_data || heatmapData;

  useEffect(() => {
    analyticsApi
      .getSummary()
      .then((data) => setAnalytics(data as unknown as AnalyticsData))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleDownloadPDF = async () => {
    setDownloading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/v1/analytics/report/pdf`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!response.ok) {
        throw new Error('Failed to generate report');
      }
      const blob = await response.blob();
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
    } finally {
      setDownloading(false);
    }
  };

  const bestModel = analytics?.models_used
    ? Object.entries(analytics.models_used).sort((a, b) => b[1] - a[1])[0]
    : null;

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
              Historical trends, model performance, and consumption insights
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
              label: 'Most Used Model',
              value: loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : (bestModel ? bestModel[0] : '—'),
              trend: bestModel ? `${bestModel[1]} runs` : '—',
              icon: Target,
              positive: true,
            },
            {
              label: 'Active Alerts',
              value: loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : (analytics ? analytics.unacknowledged_alerts.toString() : '—'),
              trend: analytics ? `${analytics.total_alerts} total` : '—',
              icon: TrendingUp,
              positive: false,
            },
            {
              label: 'Total Forecasts',
              value: loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : (analytics ? analytics.total_forecasts.toString() : '—'),
              trend: 'All time',
              icon: Layers,
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
              id="analytics-tab-models"
              value="models"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400"
            >
              Model Performance
            </TabsTrigger>
            <TabsTrigger
              id="analytics-tab-heatmap"
              value="heatmap"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400"
            >
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
                    <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500/20 bg-amber-500/10">Demo Data</Badge>
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
                          name="Actual"
                        />
                        <Bar
                          dataKey="predicted"
                          fill="#06B6D4"
                          radius={[4, 4, 0, 0]}
                          name="Predicted"
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
                    <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500/20 bg-amber-500/10">Demo Data</Badge>
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
                          name="Weekday"
                        />
                        <Area
                          type="monotone"
                          dataKey="weekend"
                          stroke="#10B981"
                          strokeWidth={2}
                          fill="url(#gradWeekend)"
                          name="Weekend"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Model Performance Tab */}
          <TabsContent value="models" className="space-y-6 mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Accuracy Over Time */}
              <Card className="glass-card border-white/[0.06]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-white flex items-center justify-between w-full">
                    <span>Model R² Score Over Time</span>
                    <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500/20 bg-amber-500/10">Demo Data</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={analytics?.monthly_accuracy || monthlyAccuracy}>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(59,130,246,0.06)"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="month"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748B', fontSize: 12 }}
                        />
                        <YAxis
                          domain={[0.6, 0.9]}
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748B', fontSize: 12 }}
                          width={40}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#111827',
                            border: '1px solid rgba(59,130,246,0.15)',
                            borderRadius: '12px',
                            color: '#E2E8F0',
                          }}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="cnn_bilstm"
                          stroke="#3B82F6"
                          strokeWidth={2}
                          dot={{ r: 4, fill: '#3B82F6' }}
                          name="CNN-BiLSTM"
                        />
                        <Line
                          type="monotone"
                          dataKey="sota_hybrid"
                          stroke="#06B6D4"
                          strokeWidth={2}
                          dot={{ r: 4, fill: '#06B6D4' }}
                          name="SOTA Hybrid"
                        />
                        <Line
                          type="monotone"
                          dataKey="patchtst"
                          stroke="#10B981"
                          strokeWidth={2}
                          dot={{ r: 4, fill: '#10B981' }}
                          name="PatchTST"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Radar Chart */}
              <Card className="glass-card border-white/[0.06]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-white flex items-center justify-between w-full">
                    <span>Model Comparison Radar</span>
                    <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500/20 bg-amber-500/10">Demo Data</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[320px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={analytics?.model_performance || modelPerformance}>
                        <PolarGrid stroke="rgba(59,130,246,0.1)" />
                        <PolarAngleAxis
                          dataKey="metric"
                          tick={{ fill: '#64748B', fontSize: 11 }}
                        />
                        <PolarRadiusAxis
                          tick={{ fill: '#64748B', fontSize: 10 }}
                          domain={[0, 100]}
                        />
                        <Radar
                          name="CNN-BiLSTM"
                          dataKey="cnn_bilstm"
                          stroke="#3B82F6"
                          fill="#3B82F6"
                          fillOpacity={0.1}
                        />
                        <Radar
                          name="SOTA Hybrid"
                          dataKey="sota_hybrid"
                          stroke="#06B6D4"
                          fill="#06B6D4"
                          fillOpacity={0.1}
                        />
                        <Radar
                          name="PatchTST"
                          dataKey="patchtst"
                          stroke="#10B981"
                          fill="#10B981"
                          fillOpacity={0.1}
                        />
                        <Legend />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Heatmap Tab */}
          <TabsContent value="heatmap" className="space-y-6 mt-6">
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-white flex items-center justify-between w-full">
                  <span>Weekly Consumption Heatmap</span>
                  <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500/20 bg-amber-500/10">Demo Data</Badge>
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
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
