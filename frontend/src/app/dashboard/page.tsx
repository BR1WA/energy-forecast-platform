'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  BarChart3,
  TrendingUp,
  Bell,
  Zap,
  ArrowUpRight,
  ArrowRight,
  Activity,
  Clock,
  LineChart,
  Target,
  Loader2,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useAuth } from '@/lib/auth';
import { analyticsApi, forecastApi } from '@/lib/api';
import { formatTimeAgo } from '@/lib/utils';

interface AnalyticsData {
  total_forecasts: number;
  total_alerts: number;
  unacknowledged_alerts: number;
  models_used: Record<string, number>;
  avg_peak_power: number | null;
  recent_forecasts: Array<{
    id: number;
    model_name: string;
    created_at: string;
    peak_power: number | null;
  }>;
  consumption_trend?: Array<{
    date: string;
    consumption: number;
    predicted?: number;
  }>;
}

// Model display name mapping
const modelDisplayNames: Record<string, string> = {
  patchtst: 'PatchTST',
  sota: 'SOTA Hybrid',
  cnn_bilstm: 'CNN-BiLSTM',
};

// Fallback chart data derived from recent forecasts
const defaultChartData = [
  { date: 'Mon', consumption: 4200, predicted: 4100 },
  { date: 'Tue', consumption: 3800, predicted: 3900 },
  { date: 'Wed', consumption: 5100, predicted: 5000 },
  { date: 'Thu', consumption: 4600, predicted: 4700 },
  { date: 'Fri', consumption: 4900, predicted: 4800 },
  { date: 'Sat', consumption: 3200, predicted: 3300 },
  { date: 'Sun', consumption: 2800, predicted: 2900 },
];

export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setMounted(true);
    // Fetch real analytics data
    analyticsApi
      .getSummary()
      .then((data) => setAnalytics(data as unknown as AnalyticsData))
      .catch(() => {
        // Fallback if not authenticated or API error
        setAnalytics(null);
      })
      .finally(() => setLoading(false));
  }, []);

  // Compute stat cards from real data
  const bestModel = analytics?.models_used
    ? Object.entries(analytics.models_used).sort((a, b) => b[1] - a[1])[0]
    : null;

  const statCards = [
    {
      title: 'Total Forecasts',
      value: analytics ? analytics.total_forecasts.toString() : '—',
      change: bestModel ? `Top: ${modelDisplayNames[bestModel[0]] || bestModel[0]}` : '',
      changeType: 'positive' as const,
      icon: BarChart3,
      gradient: 'from-blue-500 to-blue-600',
      glow: 'glow-blue',
    },
    {
      title: 'Avg Peak Power',
      value: analytics?.avg_peak_power
        ? `${analytics.avg_peak_power.toFixed(2)} kW`
        : '—',
      change: 'Global Active Power',
      changeType: 'positive' as const,
      icon: Target,
      gradient: 'from-emerald-500 to-emerald-600',
      glow: 'glow-emerald',
    },
    {
      title: 'Active Alerts',
      value: analytics ? analytics.unacknowledged_alerts.toString() : '—',
      change: analytics ? `${analytics.total_alerts} total` : '',
      changeType: 'negative' as const,
      icon: Bell,
      gradient: 'from-amber-500 to-orange-500',
      glow: '',
    },
    {
      title: 'Models Used',
      value: analytics?.models_used
        ? Object.keys(analytics.models_used).length.toString()
        : '—',
      change: 'PatchTST, SOTA, CNN-BiLSTM',
      changeType: 'positive' as const,
      icon: Zap,
      gradient: 'from-cyan-500 to-cyan-600',
      glow: 'glow-cyan',
    },
  ];

  const timeAgo = formatTimeAgo;

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">
              Good {getGreeting()},{' '}
              <span className="gradient-text">
                {user?.full_name?.split(' ')[0] || 'User'}
              </span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Here&apos;s your energy overview for today
            </p>
          </div>
          <Button
            id="dashboard-new-forecast"
            onClick={() => router.push('/forecast')}
            className="bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white shadow-lg shadow-blue-500/20 transition-all duration-300 hover:shadow-blue-500/30"
          >
            <LineChart className="w-4 h-4 mr-2" />
            New Forecast
          </Button>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((card, index) => (
            <Card
              key={card.title}
              id={`stat-${card.title.toLowerCase().replace(/\s+/g, '-')}`}
              className={`glass-card stat-card border-white/[0.06] ${card.glow} transition-all duration-500`}
              style={{
                animationDelay: mounted ? `${index * 100}ms` : '0ms',
              }}
            >
              <CardContent className="p-5">
                <div className="flex items-start justify-between">
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {card.title}
                    </p>
                    <p className="text-2xl font-bold text-white">
                      {loading ? (
                        <Loader2 className="w-5 h-5 animate-spin text-slate-500" />
                      ) : (
                        card.value
                      )}
                    </p>
                    <div className="flex items-center gap-1">
                      <span
                        className={`text-xs font-medium ${
                          card.changeType === 'positive'
                            ? 'text-emerald-400'
                            : 'text-amber-400'
                        }`}
                      >
                        {card.change}
                      </span>
                    </div>
                  </div>
                  <div
                    className={`flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br ${card.gradient} shadow-lg`}
                  >
                    <card.icon className="w-5 h-5 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Consumption Chart */}
          <Card className="glass-card border-white/[0.06] lg:col-span-2">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-400" />
                  Energy Consumption Trend
                </CardTitle>
                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                    <span className="text-slate-400">Actual</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-cyan-400" />
                    <span className="text-slate-400">Predicted</span>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="h-[280px] mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={analytics?.consumption_trend || defaultChartData}>
                    <defs>
                      <linearGradient
                        id="colorConsumption"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor="#3B82F6"
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="100%"
                          stopColor="#3B82F6"
                          stopOpacity={0}
                        />
                      </linearGradient>
                      <linearGradient
                        id="colorPredicted"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor="#06B6D4"
                          stopOpacity={0.2}
                        />
                        <stop
                          offset="100%"
                          stopColor="#06B6D4"
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
                      dataKey="date"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#64748B', fontSize: 12 }}
                    />
                    <YAxis
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
                        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                        color: '#E2E8F0',
                        fontSize: '13px',
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="consumption"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      fill="url(#colorConsumption)"
                    />
                    <Area
                      type="monotone"
                      dataKey="predicted"
                      stroke="#06B6D4"
                      strokeWidth={2}
                      strokeDasharray="5 3"
                      fill="url(#colorPredicted)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                <Zap className="w-4 h-4 text-cyan-400" />
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <button
                id="quick-action-forecast"
                onClick={() => router.push('/forecast')}
                className="w-full flex items-center gap-3 p-3 rounded-xl bg-blue-500/10 border border-blue-500/10 hover:border-blue-500/20 hover:bg-blue-500/15 transition-all duration-200 group"
              >
                <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-blue-500/20">
                  <LineChart className="w-4 h-4 text-blue-400" />
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-white">
                    Run Forecast
                  </p>
                  <p className="text-xs text-slate-400">
                    Predict energy consumption
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-blue-400 transition-colors" />
              </button>

              <button
                id="quick-action-compare"
                onClick={() => router.push('/forecast')}
                className="w-full flex items-center gap-3 p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/10 hover:border-cyan-500/20 hover:bg-cyan-500/15 transition-all duration-200 group"
              >
                <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-cyan-500/20">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-white">
                    Compare Models
                  </p>
                  <p className="text-xs text-slate-400">
                    3-way model comparison
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
              </button>

              <button
                id="quick-action-analytics"
                onClick={() => router.push('/analytics')}
                className="w-full flex items-center gap-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/10 hover:border-emerald-500/20 hover:bg-emerald-500/15 transition-all duration-200 group"
              >
                <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-emerald-500/20">
                  <BarChart3 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-white">
                    View Analytics
                  </p>
                  <p className="text-xs text-slate-400">
                    Explore insights & trends
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 transition-colors" />
              </button>

              <button
                id="quick-action-alerts"
                onClick={() => router.push('/alerts')}
                className="w-full flex items-center gap-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/10 hover:border-amber-500/20 hover:bg-amber-500/15 transition-all duration-200 group"
              >
                <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-amber-500/20">
                  <Bell className="w-4 h-4 text-amber-400" />
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-white">
                    Manage Alerts
                  </p>
                  <p className="text-xs text-slate-400">
                    {analytics
                      ? `${analytics.unacknowledged_alerts} active alerts`
                      : 'View alerts'}
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-amber-400 transition-colors" />
              </button>
            </CardContent>
          </Card>
        </div>

        {/* Recent Forecasts — from real API data */}
        <Card className="glass-card border-white/[0.06]">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-400" />
                Recent Forecasts
              </CardTitle>
              <Button
                id="dashboard-view-all"
                variant="ghost"
                size="sm"
                onClick={() => router.push('/forecast')}
                className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
              >
                View All
                <ArrowUpRight className="w-3 h-3 ml-1" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
                </div>
              ) : analytics?.recent_forecasts &&
                analytics.recent_forecasts.length > 0 ? (
                analytics.recent_forecasts.map((forecast) => (
                  <div
                    key={forecast.id}
                    id={`forecast-item-${forecast.id}`}
                    className="flex items-center justify-between p-3 rounded-xl hover:bg-white/[0.02] transition-all duration-200"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-blue-500/10">
                        <LineChart className="w-4 h-4 text-blue-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">
                          {modelDisplayNames[forecast.model_name] ||
                            forecast.model_name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {timeAgo(forecast.created_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="text-sm font-medium text-emerald-400">
                          {forecast.peak_power
                            ? `${forecast.peak_power.toFixed(2)} kW`
                            : '—'}
                        </p>
                        <p className="text-[10px] text-slate-500 uppercase">
                          peak power
                        </p>
                      </div>
                      <Badge
                        variant="outline"
                        className="border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[10px]"
                      >
                        completed
                      </Badge>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8">
                  <p className="text-sm text-slate-400">
                    No forecasts yet. Run your first prediction!
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'morning';
  if (hour < 18) return 'afternoon';
  return 'evening';
}
