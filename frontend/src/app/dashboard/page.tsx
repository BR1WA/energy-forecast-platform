'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/lib/auth';
import { getAccessToken, dashboardApi, analyticsApi } from '@/lib/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { cn } from '@/lib/utils';
import {
  Zap,
  Activity,
  Cpu,
  Thermometer,
  PlayCircle,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  Home,
  Users,
  FileText,
  DollarSign,
  Clock,
  RefreshCw,
  Sun,
  Wind,
  Target,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  BarChart3,
  Download,
  Star,
  Shield,
  Gauge,
  Lightbulb,
  CircleDot,
  Radar,
  Brain,
  ArrowDown,
  ArrowUp
} from 'lucide-react';
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

// ── Telemetry frame interface ──────────────────────────────────────────
interface TelemetryFrame {
  timestamp: string;
  gap: number;
  grp: number;
  voltage: number;
  intensity: number;
  sub_metering_1: number;
  sub_metering_2: number;
  sub_metering_3: number;
  predictions?: number[];
}

// ── Animated Counter Hook ──────────────────────────────────────────────
function useCountUp(target: number, duration: number = 600): number {
  const [current, setCurrent] = useState(0);
  const prevTarget = useRef(target);

  useEffect(() => {
    const from = prevTarget.current;
    prevTarget.current = target;
    if (from === target) { setCurrent(target); return; }

    const start = performance.now();
    let raf: number;

    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(from + (target - from) * eased);
      if (progress < 1) raf = requestAnimationFrame(animate);
    };

    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return current;
}

// ── Energy Score Gauge SVG ─────────────────────────────────────────────
function EnergyScoreGauge({ score }: { score: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const animatedScore = useCountUp(score);
  const offset = circumference - (animatedScore / 100) * circumference;

  const color = animatedScore >= 80 ? '#10B981' : animatedScore >= 60 ? '#F59E0B' : '#EF4444';

  return (
    <div className="relative w-28 h-28 flex-shrink-0">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
        <circle
          cx="50" cy="50" r={radius} fill="none"
          stroke={color} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
          style={{ filter: `drop-shadow(0 0 8px ${color}40)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-black text-white font-mono">{Math.round(animatedScore)}</span>
        <span className="text-[8px] text-slate-400 font-bold uppercase tracking-widest">Score</span>
      </div>
    </div>
  );
}

// ── Star Icon ──────────────────────────────────────────────────────────
function StarIcon({ filled }: { filled: boolean }) {
  return (
    <Star className={cn("w-3 h-3", filled ? "fill-amber-400 text-amber-400" : "text-slate-700")} />
  );
}

// ── Main Dashboard Component ───────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);

  // Geolocation and resolved states
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locationResolved, setLocationResolved] = useState(false);

  // Dashboard summary state
  const [summary, setSummary] = useState<any>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // WebSocket live telemetry
  const [liveData, setLiveData] = useState<TelemetryFrame | null>(null);
  const [history, setHistory] = useState<TelemetryFrame[]>([]);

  // Chart mode
  const [dashboardTimeframe, setDashboardTimeframe] = useState<'live' | '24'>('live');

  // Request user geolocation once on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setCoords({
            lat: position.coords.latitude,
            lon: position.coords.longitude,
          });
          setLocationResolved(true);
        },
        (error) => {
          console.warn('Geolocation error or permission denied:', error);
          setLocationResolved(true);
        },
        {
          enableHighAccuracy: false,
          timeout: 5000,
          maximumAge: 300000
        }
      );
    } else {
      setLocationResolved(true);
    }
  }, []);

  // Fetch dashboard summary
  const fetchSummary = useCallback(async () => {
    try {
      const data = coords 
        ? await dashboardApi.getSummary(coords.lat, coords.lon)
        : await dashboardApi.getSummary();
      setSummary(data);
      setSummaryError(null);
    } catch (err: any) {
      setSummaryError(err.message || 'Failed to load');
    } finally {
      setSummaryLoading(false);
    }
  }, [coords]);

  useEffect(() => {
    setMounted(true);
    // Only query backend after geolocation resolution completes to avoid Casablanca flickers
    if (locationResolved) {
      fetchSummary();
      const interval = setInterval(fetchSummary, 5000);
      return () => clearInterval(interval);
    }
  }, [locationResolved, fetchSummary]);

  // WebSocket URL
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  useEffect(() => {
    const token = getAccessToken();
    if (token && typeof window !== 'undefined') {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = window.location.hostname;
      setWsUrl(`${protocol}://${host}:8000/api/v1/forecast/smart-meter/live-ws?token=${token}`);
    }
  }, []);

  useWebSocket(wsUrl, {
    onMessage: (event: MessageEvent) => {
      try {
        const frame: TelemetryFrame = JSON.parse(event.data);
        setLiveData(frame);
        setHistory((prev) => [...prev, frame].slice(-50));
      } catch (err) {
        console.error('[DASHBOARD-WS] Parse error:', err);
      }
    },
  });

  // Chart data
  const chartData = history.map((item) => ({
    time: new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    consumption: item.gap,
    predicted: item.predictions ? item.predictions[0] : null
  }));

  const activePower = liveData?.gap || 0.0;

  if (!mounted) return null;

  // ── Extracted data ─────────────────────────────────────────────────
  const exec = summary?.executive;
  const assistant = summary?.assistant;
  const liveStatus = summary?.live_status;
  const liveCons = summary?.live_consumption;
  const energyFlow = summary?.energy_flow;
  const forecast = summary?.forecast;
  const recs = summary?.recommendations;
  const budget = summary?.budget;
  const weather = summary?.weather;
  const radar = summary?.intelligence_radar;
  const todayVsYesterday = summary?.today_vs_yesterday;
  const aiDecisions = summary?.ai_decisions;
  const firstName = user?.full_name?.trim().split(/\s+/)[0] || 'there';

  // ── Skeleton Loader ────────────────────────────────────────────────
  if (summaryLoading) {
    return (
      <AppLayout>
        <div className="p-6 max-w-7xl mx-auto space-y-6">
          {/* Hero skeleton */}
          <div className="h-52 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
          {/* AI Command Center skeleton */}
          <div className="h-40 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
          {/* Grid skeleton */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="h-72 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
            <div className="lg:col-span-2 h-72 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
          </div>
          {/* Bottom row skeleton */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 h-52 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
            <div className="h-52 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="h-44 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
            <div className="h-44 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
            <div className="h-44 bg-[#111827]/60 rounded-2xl border border-white/5 animate-pulse" />
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">

        {summaryError && (
          <div role="alert" className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            Dashboard data is temporarily unavailable: {summaryError}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* COMPONENT A — EXECUTIVE HERO                                  */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        <Card className="relative overflow-hidden border-none bg-gradient-to-br from-slate-900 via-indigo-950/80 to-slate-950 shadow-2xl">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-500/10 via-transparent to-transparent pointer-events-none" />
          <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-600/5 rounded-full blur-3xl pointer-events-none" />
          <CardContent className="relative z-10 p-6 lg:p-8">
            {/* Greeting + KPIs Row */}
            <div className="flex flex-col lg:flex-row lg:items-center gap-6">
              {/* Left: Gauge + Greeting */}
              <div className="flex items-center gap-5 flex-shrink-0">
                <EnergyScoreGauge score={exec?.energy_score || 0} />
                <div className="space-y-1.5">
                  <h1 className="text-xl font-bold text-white tracking-tight">
                    {exec?.greeting || 'Hello'}, <span className="text-indigo-400">{firstName}</span>
                  </h1>
                  <p className="text-sm text-slate-300 max-w-lg leading-relaxed">
                    {exec?.proactive_sentence || exec?.summary_sentence || 'Your household is operating efficiently.'}
                  </p>
                  <div className="flex items-center gap-2 pt-0.5">
                    <Badge className="bg-indigo-600/20 text-indigo-300 border-indigo-500/20 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5">
                      {exec?.current_tariff_tier || 'Tranche 2'}
                    </Badge>
                    {weather && (
                      <Badge className="bg-amber-600/15 text-amber-300 border-amber-500/20 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5">
                        <Thermometer className="w-2.5 h-2.5 mr-1" />{weather.temperature}°C · {weather.condition}
                      </Badge>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: KPI Cards with Trends */}
              <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-3 lg:gap-4">
                <KPICard icon={<DollarSign className="w-4 h-4" />} label="Estimated Bill" value={`${exec?.estimated_bill || 0}`} unit="MAD" color="text-emerald-400" bgColor="bg-emerald-600/10" delta={exec?.bill_delta} deltaUnit="MAD" />
                <KPICard icon={<Sparkles className="w-4 h-4" />} label="Potential Savings" value={`${exec?.potential_savings || 0}`} unit="MAD" color="text-amber-400" bgColor="bg-amber-600/10" />
                <KPICard icon={<Shield className="w-4 h-4" />} label="Forecast" value={`${radar?.confidence?.pct ?? 0}%`} unit="" color="text-indigo-400" bgColor="bg-indigo-600/10" isText subtitle={radar?.confidence?.basis || 'Not calibrated'} />
              </div>
            </div>

            {/* Today's Story */}
            {exec?.today_story && exec.today_story.length > 0 && (
              <div className="mt-5 pt-5 border-t border-white/[0.06]">
                <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Today&apos;s Story</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {exec.today_story.map((item: any, i: number) => (
                    <div key={i} className="flex items-center gap-2.5 text-sm">
                      {item.icon === 'check' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                      )}
                      <span className="text-slate-300 text-xs font-medium leading-snug">{item.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* HOUSE INTELLIGENCE RADAR — Flagship Centerpiece                */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {radar && (
          <Card className="relative overflow-hidden glass-card border-white/[0.06] bg-gradient-to-r from-slate-900/80 via-indigo-950/20 to-slate-900/80">
            <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-emerald-500/30 to-transparent" />
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="p-2 bg-emerald-600/15 rounded-lg text-emerald-400">
                  <Radar className="w-5 h-5" />
                </div>
                <h2 className="text-sm font-bold text-white tracking-wide">Current Household Status</h2>
              </div>

              {/* Radar Dimensions */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
                {radar.dimensions?.map((dim: any, i: number) => {
                  const dotColor = dim.status === 'green' ? 'bg-emerald-400' : dim.status === 'amber' ? 'bg-amber-400' : dim.status === 'red' ? 'bg-rose-400' : 'bg-blue-400';
                  const textColor = dim.status === 'green' ? 'text-emerald-400' : dim.status === 'amber' ? 'text-amber-400' : dim.status === 'red' ? 'text-rose-400' : 'text-blue-400';
                  return (
                    <div key={i} className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.05] text-center hover:bg-white/[0.04] transition-all">
                      <div className="flex items-center justify-center gap-1.5 mb-2">
                        <span className={cn("w-2 h-2 rounded-full", dotColor)} />
                        <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">{dim.label}</span>
                      </div>
                      <span className={cn("text-xl font-black font-mono", textColor)}>
                        {typeof dim.value === 'number' ? dim.value : dim.value}
                      </span>
                      {dim.unit && <span className="text-[9px] text-slate-500 ml-0.5">{dim.unit}</span>}
                    </div>
                  );
                })}
              </div>

              {/* Overall Condition */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-xl bg-[#0A0F1C]/60 border border-white/[0.04]">
                <div className="flex items-center gap-2">
                  <Badge className={cn(
                    "text-[10px] font-bold uppercase tracking-wider px-3 py-1",
                    radar.condition === 'Excellent' ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/20'
                      : radar.condition === 'Good' ? 'bg-blue-600/20 text-blue-300 border-blue-500/20'
                      : radar.condition === 'Fair' ? 'bg-amber-600/20 text-amber-300 border-amber-500/20'
                      : 'bg-rose-600/20 text-rose-300 border-rose-500/20'
                  )}>
                    {radar.condition}
                  </Badge>
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Overall Condition</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{radar.message}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* COMPONENT B — AI COMMAND CENTER                                */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        <Card className="glass-card border-white/[0.06] bg-gradient-to-r from-indigo-950/30 to-slate-900/50 overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-indigo-500/40 to-transparent" />
          <CardContent className="p-6 space-y-4 relative">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-indigo-600/20 rounded-xl text-indigo-400 shrink-0 relative">
                <Cpu className="w-6 h-6" />
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
              </div>
              <div className="space-y-3 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-white tracking-wide">EnergyAI Assistant</h3>
                  <Badge className="bg-indigo-600 text-white text-[8px] uppercase font-mono px-2 py-0.5">Live</Badge>
                </div>

                {/* Structured Narrative */}
                <div className="space-y-2.5">
                  <p className="text-base font-bold text-white">{assistant?.headline || 'Analyzing...'}</p>
                  <p className="text-sm text-slate-300 leading-relaxed">{assistant?.body}</p>

                  {assistant?.warning && (
                    <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                      <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-amber-200 leading-relaxed font-medium">{assistant.warning}</p>
                    </div>
                  )}

                  {assistant?.recommended_action && (
                    <div className="flex items-start gap-2.5 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-emerald-200 leading-relaxed font-medium">
                        <span className="text-emerald-400 font-bold">Recommended: </span>{assistant.recommended_action}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-2.5 pt-2">
              <Button onClick={() => router.push('/forecast')} size="sm" className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold h-9 rounded-lg px-4">
                <TrendingUp className="w-3.5 h-3.5 mr-2" /> View Forecast
              </Button>
              <Button onClick={() => router.push('/simulation')} size="sm" variant="outline" className="border-white/10 text-white hover:bg-white/5 text-xs font-semibold h-9 rounded-lg">
                <PlayCircle className="w-3.5 h-3.5 mr-2" /> Run Simulation
              </Button>
              <Button onClick={() => router.push('/recommendations')} size="sm" variant="outline" className="border-white/10 text-white hover:bg-white/5 text-xs font-semibold h-9 rounded-lg">
                <Lightbulb className="w-3.5 h-3.5 mr-2" /> Recommendations
              </Button>
              <Button onClick={() => router.push('/reports')} size="sm" variant="outline" className="border-white/10 text-white hover:bg-white/5 text-xs font-semibold h-9 rounded-lg">
                <FileText className="w-3.5 h-3.5 mr-2" /> View Report
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* COMPONENT C + D — LIVE HOUSE + ENERGY FLOW & CHART            */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── Component C: Live House Digital Twin ─────────────────── */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Home className="w-4 h-4 text-indigo-400" />
                Home Status
                <span className="ml-auto flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-[9px] text-emerald-400 font-bold uppercase">Live</span>
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 pb-4">
              {/* Room-based appliance status */}
              {liveStatus?.appliances?.map((item: any, i: number) => {
                const isActive = item.status === 'Running' || item.status === 'Generating' || item.status === 'Normal';
                const room = item.name === 'Air Conditioner' ? 'Living Room'
                  : item.name === 'Washing Machine' ? 'Kitchen'
                  : item.name === 'Solar Panels' ? 'Roof'
                  : item.name === 'Occupancy' ? 'Home'
                  : 'General';
                const icon = item.name === 'Air Conditioner' ? <Wind className="w-3.5 h-3.5" />
                  : item.name === 'Washing Machine' ? <RefreshCw className="w-3.5 h-3.5" />
                  : item.name === 'Solar Panels' ? <Sun className="w-3.5 h-3.5" />
                  : item.name === 'Occupancy' ? <Users className="w-3.5 h-3.5" />
                  : <Lightbulb className="w-3.5 h-3.5" />;

                return (
                  <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-colors group">
                    <div className={cn(
                      "p-1.5 rounded-lg",
                      isActive ? "bg-emerald-600/15 text-emerald-400" : "bg-slate-800/50 text-slate-500"
                    )}>
                      {icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">{room}</p>
                      <p className="text-xs text-white font-medium truncate">{item.name}</p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className={cn(
                        "w-1.5 h-1.5 rounded-full",
                        isActive ? "bg-emerald-400 animate-pulse" : "bg-slate-600"
                      )} />
                      <Badge variant="outline" className={cn(
                        "text-[8px] font-mono px-1.5 border-white/10",
                        isActive ? "text-emerald-300" : "text-slate-500"
                      )}>
                        {item.status === 'Generating' ? `${item.level}` : item.level}
                      </Badge>
                    </div>
                  </div>
                );
              })}

              {/* Load metrics */}
              <div className="mt-3 p-3 rounded-xl bg-[#0A0F1C]/80 border border-white/[0.04] grid grid-cols-2 gap-2.5">
                <LoadMetric label="Power" value={`${liveStatus?.load?.active_power || 0}`} unit="kW" />
                <LoadMetric label="Voltage" value={`${liveStatus?.load?.voltage ?? 'N/A'}`} unit="V" />
                <LoadMetric label="Current" value={`${liveStatus?.load?.current || 0}`} unit="A" />
                <LoadMetric label="Frequency" value={`${liveStatus?.load?.frequency ?? 'N/A'}`} unit="Hz" />
              </div>
            </CardContent>
          </Card>

          {/* ── Component D: Energy Flow + Live Chart ────────────────── */}
          <Card className="glass-card border-white/[0.06] lg:col-span-2 flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                    Live Energy Flow
                  </CardTitle>
                  <CardDescription className="text-[10px] text-slate-500 mt-0.5">Real-time energy production, consumption, and grid exchange.</CardDescription>
                </div>
                <div className="flex bg-[#111827] border border-white/10 rounded-lg p-0.5 select-none">
                  {[
                    { value: 'live', label: 'Live Stream' },
                    { value: '24', label: '24h Forecast' },
                  ].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setDashboardTimeframe(opt.value as any)}
                      className={cn(
                        "px-3 py-1 text-[10px] font-bold rounded-md transition-all",
                        dashboardTimeframe === opt.value
                          ? "bg-indigo-600 text-white shadow-md"
                          : "text-slate-400 hover:text-white hover:bg-white/5"
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 flex-1 flex flex-col pb-4">
              {/* Energy Flow Diagram */}
              <div className="flex items-center justify-center gap-3 py-3 px-4 rounded-xl bg-[#0A0F1C]/60 border border-white/[0.04]">
                <FlowNode icon={<Sun className="w-5 h-5" />} label="Solar" value={`${energyFlow?.solar_generation || 0} kW`} color="text-amber-400" bgColor="bg-amber-600/15" active={energyFlow?.solar_generation > 0} />
                <FlowArrow active={energyFlow?.solar_generation > 0} color="amber" />
                <FlowNode icon={<Home className="w-5 h-5" />} label="House" value={`${energyFlow?.house_consumption || activePower} kW`} color="text-indigo-400" bgColor="bg-indigo-600/15" active />
                <FlowArrow active color="rose" reverse />
                <FlowNode icon={<Zap className="w-5 h-5" />} label="Grid" value={`${energyFlow?.grid_import || activePower} kW`} color="text-rose-400" bgColor="bg-rose-600/15" active />
                {energyFlow?.solar_offset_pct > 0 && (
                  <div className="ml-3 px-3 py-1.5 rounded-lg bg-emerald-600/10 border border-emerald-500/20">
                    <p className="text-[10px] text-emerald-400 font-bold">{energyFlow.solar_offset_pct}% Solar Offset</p>
                  </div>
                )}
              </div>

              {/* Chart */}
              <div className="flex-1 min-h-[200px]">
                {dashboardTimeframe === 'live' ? (
                  chartData.length === 0 ? (
                    <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 bg-[#0A0F1C]/40 border border-white/5 rounded-xl min-h-[200px]">
                      <RefreshCw className="w-8 h-8 animate-spin text-slate-600 mb-2" />
                      <p className="text-xs font-semibold">Waiting for telemetry connection...</p>
                      <p className="text-[10px] text-slate-600 mt-0.5">Start the Virtual House simulator to see live data.</p>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(16,185,129,0.06)" vertical={false} />
                        <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 10 }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} domain={[0, 'auto']} />
                        <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid rgba(16,185,129,0.15)', borderRadius: '12px', color: '#E2E8F0', fontSize: '11px' }} />
                        <Line type="monotone" dataKey="consumption" stroke="#10B981" strokeWidth={3} dot={false} activeDot={{ r: 6, fill: '#10B981', stroke: '#111827', strokeWidth: 2 }} isAnimationActive animationDuration={300} />
                      </LineChart>
                    </ResponsiveContainer>
                  )
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={forecast?.points || []}>
                      <defs>
                        <linearGradient id="cmdGradPred" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10B981" stopOpacity={0.15} />
                          <stop offset="100%" stopColor="#10B981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(59,130,246,0.06)" vertical={false} />
                      <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 10 }} />
                      <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} domain={[0, 'auto']} />
                      <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid rgba(59,130,246,0.15)', borderRadius: '12px', color: '#E2E8F0', fontSize: '11px' }} />
                      <Area type="monotone" dataKey="predicted" stroke="#10B981" strokeWidth={2} strokeDasharray="5 3" fill="url(#cmdGradPred)" name="Predicted (kW)" isAnimationActive animationDuration={300} />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Stats bar */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MiniStat label="Current Power" value={`${liveCons?.current_power || activePower}`} unit="kW" />
                <MiniStat label="Today's Energy" value={`${liveCons?.today_energy || 0}`} unit="kWh" />
                <MiniStat label="Today's Peak" value={`${liveCons?.today_peak || 0}`} unit="kW" />
                <MiniStat label="Avg Load" value={`${liveCons?.average_load || 0}`} unit="kW" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* COMPONENT E + F — FORECAST TIMELINE + BUDGET MISSION          */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── Component E: Forecast Timeline ──────────────────────── */}
          <Card className="glass-card border-white/[0.06] lg:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-400" />
                Forecast Timeline
              </CardTitle>
              <CardDescription className="text-[10px] text-slate-500">Upcoming energy events and tomorrow&apos;s outlook.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pb-5">
              {/* Timeline */}
              <div className="relative">
                <div className="absolute left-3 top-0 bottom-0 w-[1px] bg-gradient-to-b from-indigo-500/40 via-indigo-500/20 to-transparent" />
                <div className="space-y-3 pl-8">
                  <TimelineEvent time="Now" label="Current consumption" detail={`${liveCons?.current_power || 0} kW`} severity="live" />
                  {forecast?.peak_hour && <TimelineEvent time={forecast.peak_hour} label="Forecast peak" detail="From the persisted forecast" severity="warning" />}
                  {weather?.temperature !== undefined && weather?.temperature !== null && (
                    <TimelineEvent time="Now" label="Observed temperature" detail={`${weather.temperature}°C`} severity="info" />
                  )}
                </div>
              </div>

              {/* Tomorrow's Outlook */}
              <div className="p-4 rounded-xl bg-[#0A0F1C]/60 border border-white/[0.04] grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Expected Peak</p>
                  <p className="text-sm font-bold text-white mt-0.5">{forecast?.peak_hour || 'Not available'}</p>
                </div>
                <div>
                  <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Est. Cost</p>
                  <p className="text-sm font-bold text-white mt-0.5">{forecast?.estimated_cost || 0} <span className="text-[10px] text-slate-500">MAD</span></p>
                </div>
                <div>
                  <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Confidence</p>
                  <p className="text-sm font-bold text-emerald-400 mt-0.5">{forecast?.forecast_reliability || 'Not available'}</p>
                </div>
                <div>
                  <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">Reason</p>
                  <p className="text-xs text-slate-400 mt-0.5 leading-snug">{forecast?.explainability || 'No forecast available'}</p>
                </div>
              </div>

              {/* Forecast Validation */}
              {forecast?.validation?.available && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/10">
                  <Gauge className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <div className="flex-1 text-xs">
                    <span className="text-slate-400">Yesterday&apos;s forecast accuracy: </span>
                    <span className="text-white font-bold">Predicted {forecast.validation.predicted} kW</span>
                    <span className="text-slate-500"> vs </span>
                    <span className="text-white font-bold">Actual {forecast.validation.actual} kW</span>
                    <span className={cn(
                      "ml-2 font-bold",
                      forecast.validation.error_pct < 10 ? "text-emerald-400" : "text-amber-400"
                    )}>
                      ({forecast.validation.error_pct}% error)
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Component F: Budget Mission ──────────────────────────── */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Target className="w-4 h-4 text-emerald-400" />
                Budget Mission
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center space-y-4 pb-5">
              {/* Circular Progress Ring */}
              <BudgetRing
                progress={budget?.progress_pct || 0}
                current={budget?.current_cost || 0}
                target={budget?.target ?? 0}
              />

              {/* Mission Status */}
              <Badge className={cn(
                "text-[10px] font-bold uppercase tracking-wider px-3 py-1",
                budget?.mission_status === 'On Track' ? "bg-emerald-600/20 text-emerald-300 border-emerald-500/20"
                  : budget?.mission_status === 'At Risk' ? "bg-amber-600/20 text-amber-300 border-amber-500/20"
                  : "bg-rose-600/20 text-rose-300 border-rose-500/20"
              )}>
                {budget?.mission_status || 'On Track'}
              </Badge>

              <div className="text-center space-y-0.5">
                <p className="text-xs text-slate-400">Remaining: <span className="text-white font-bold">{budget?.remaining || 0} MAD</span></p>
                <p className="text-[10px] text-slate-500">Tariff: {budget?.tariff_tier || 'Tranche 2'}</p>
              </div>

              {/* Scenario Comparison */}
              <div className="w-full space-y-2 pt-2 border-t border-white/[0.06]">
                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-widest text-center">Scenario Analysis</p>
                <div className="flex justify-between items-center p-2.5 rounded-lg bg-rose-500/5 border border-rose-500/10">
                  <span className="text-[10px] text-slate-400">Without recommendations</span>
                  <span className="text-xs font-bold text-rose-400">{budget?.projected_without_recs || budget?.projected_cost || 0} MAD</span>
                </div>
                <div className="flex justify-between items-center p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                  <span className="text-[10px] text-slate-400">With recommendations</span>
                  <span className="text-xs font-bold text-emerald-400">{budget?.projected_with_recs || 0} MAD</span>
                </div>
                {(budget?.savings_if_applied || 0) > 0 && (
                  <div className="text-center">
                    <span className="text-[10px] text-emerald-400 font-bold">↓ Save {budget.savings_if_applied} MAD</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* COMPONENT G + H + I — SAVINGS + ACTIVITY + QUICK ACTIONS      */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── Component G: Savings Radar ──────────────────────────── */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Top Opportunities
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 pb-4">
              {(recs?.priority_list || []).slice(0, 3).map((rec: any, i: number) => (
                <div key={rec.id || i} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all hover:translate-y-[-1px] group">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1">
                      {Array.from({ length: 5 }).map((_, s) => (
                        <StarIcon key={s} filled={s < (rec.stars || 0)} />
                      ))}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge className={cn(
                        "text-[8px] font-bold uppercase px-1.5",
                        rec.difficulty === 'Easy' ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/20' : 'bg-amber-600/20 text-amber-300 border-amber-500/20'
                      )}>
                        {rec.difficulty}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-xs text-white font-semibold">{rec.title}</p>
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-sm font-black text-emerald-400">{rec.savings} <span className="text-[9px] font-medium text-slate-500">MAD</span></span>
                    {rec.confidence_pct && (
                      <Badge className="bg-indigo-600/15 text-indigo-300 border-indigo-500/20 text-[8px] font-bold px-1.5">
                        {rec.confidence_pct}% confident
                      </Badge>
                    )}
                  </div>
                  {rec.evidence && (
                    <p className="text-[9px] text-slate-600 mt-1.5 italic">{rec.evidence}</p>
                  )}
                </div>
              ))}

              {(recs?.potential_savings || 0) > 0 && (
                <div className="text-center pt-2 border-t border-white/[0.06]">
                  <p className="text-[10px] text-slate-500">Total Potential</p>
                  <p className="text-lg font-black text-emerald-400">{recs.potential_savings} <span className="text-xs font-medium text-slate-500">MAD/mo</span></p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Component H: AI Decisions Today ────────────────────── */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Brain className="w-4 h-4 text-indigo-400" />
                AI Decisions Today
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4">
              <div className="space-y-1.5">
                {(aiDecisions || []).map((decision: any, i: number) => (
                  <div key={i} className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-white/[0.02] transition-colors">
                    {decision.done ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <CircleDot className="w-4 h-4 text-amber-400 flex-shrink-0" />
                    )}
                    <span className={cn(
                      "text-xs font-medium leading-snug",
                      decision.done ? 'text-slate-300' : 'text-amber-300'
                    )}>{decision.text}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* ── Component I: Quick Actions Dock ─────────────────────── */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" />
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4">
              <div className="grid grid-cols-2 gap-2">
                <QuickAction icon={<PlayCircle className="w-4 h-4" />} label="Simulation" onClick={() => router.push('/simulation')} color="text-indigo-400" />
                <QuickAction icon={<TrendingUp className="w-4 h-4" />} label="Forecast" onClick={() => router.push('/forecast')} color="text-emerald-400" />
                <QuickAction icon={<FileText className="w-4 h-4" />} label="Reports" onClick={() => router.push('/reports')} color="text-blue-400" />
                <QuickAction icon={<BarChart3 className="w-4 h-4" />} label="Analytics" onClick={() => router.push('/analytics')} color="text-purple-400" />
                <QuickAction icon={<Lightbulb className="w-4 h-4" />} label="Recommend" onClick={() => router.push('/recommendations')} color="text-amber-400" />
                <QuickAction icon={<DollarSign className="w-4 h-4" />} label="Budget" onClick={() => router.push('/budget')} color="text-rose-400" />
              </div>
              <Button
                onClick={async () => {
                  try { await analyticsApi.downloadReportPDF(); } catch { /* silent */ }
                }}
                variant="outline"
                className="w-full mt-3 border-white/10 text-white hover:bg-white/5 text-xs font-semibold h-9 rounded-lg"
              >
                <Download className="w-3.5 h-3.5 mr-2" /> Export PDF Report
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* ═══════════════════════════════════════════════════════════════ */}
        {/* TODAY VS YESTERDAY — Comparison Strip                          */}
        {/* ═══════════════════════════════════════════════════════════════ */}
        {todayVsYesterday?.metrics && (
          <Card className="glass-card border-white/[0.06]">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-4 h-4 text-indigo-400" />
                <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Today vs Yesterday</h3>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {todayVsYesterday.metrics.map((m: any, i: number) => {
                  const diff = m.today - m.yesterday;
                  const improved = m.label === 'Carbon' ? diff < 0 : diff < 0;
                  return (
                    <div key={i} className="p-3 rounded-lg bg-[#0A0F1C]/60 border border-white/[0.04] text-center">
                      <p className="text-[8px] text-slate-500 font-bold uppercase tracking-wider mb-1">{m.label}</p>
                      <div className="flex items-center justify-center gap-2">
                        <div>
                          <p className="text-sm font-bold text-white font-mono">{m.today}</p>
                          <p className="text-[9px] text-slate-600">Today</p>
                        </div>
                        <div className="text-slate-600">→</div>
                        <div>
                          <p className="text-sm font-bold text-slate-500 font-mono">{m.yesterday}</p>
                          <p className="text-[9px] text-slate-600">Yesterday</p>
                        </div>
                      </div>
                      <div className={cn(
                        "flex items-center justify-center gap-0.5 mt-1.5 text-[10px] font-bold",
                        improved ? 'text-emerald-400' : 'text-rose-400'
                      )}>
                        {improved ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />}
                        {Math.abs(diff).toFixed(1)} {m.unit}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

      </div>
    </AppLayout>
  );
}

// ── Sub-Components ─────────────────────────────────────────────────────

function KPICard({ icon, label, value, unit, color, bgColor, isText, delta, deltaUnit, subtitle }: {
  icon: React.ReactNode; label: string; value: string; unit: string; color: string; bgColor: string; isText?: boolean;
  delta?: number; deltaUnit?: string; subtitle?: string;
}) {
  const numValue = isText ? 0 : parseFloat(value) || 0;
  const animated = useCountUp(numValue);

  return (
    <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition-all hover:translate-y-[-1px]">
      <div className="flex items-center gap-2 mb-2">
        <div className={cn("p-1.5 rounded-lg", bgColor, color)}>{icon}</div>
        <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-xl font-black text-white font-mono">
          {isText ? value : Math.round(animated)}
        </span>
        {unit && <span className="text-[10px] text-slate-500 font-semibold">{unit}</span>}
      </div>
      {delta !== undefined && delta !== null && delta !== 0 && (
        <div className={cn(
          "flex items-center gap-0.5 mt-1 text-[10px] font-bold",
          delta < 0 ? 'text-emerald-400' : 'text-rose-400'
        )}>
          {delta < 0 ? <ArrowDownRight className="w-3 h-3" /> : <ArrowUpRight className="w-3 h-3" />}
          {Math.abs(delta)} {deltaUnit || unit}
          <span className="text-slate-600 font-normal ml-1">vs yesterday</span>
        </div>
      )}
      {subtitle && (
        <p className="text-[9px] text-slate-600 mt-1 leading-snug">{subtitle}</p>
      )}
    </div>
  );
}

function LoadMetric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="text-center">
      <p className="text-[8px] text-slate-600 font-bold uppercase tracking-wider">{label}</p>
      <p className="text-xs font-bold text-white font-mono">{value} <span className="text-[9px] text-slate-500">{unit}</span></p>
    </div>
  );
}

function MiniStat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="p-2.5 rounded-lg bg-[#0A0F1C]/60 border border-white/[0.04] text-center">
      <p className="text-[8px] text-slate-500 font-bold uppercase tracking-wider">{label}</p>
      <p className="text-sm font-bold text-white font-mono mt-0.5">{value} <span className="text-[9px] text-slate-500">{unit}</span></p>
    </div>
  );
}

function FlowNode({ icon, label, value, color, bgColor, active }: {
  icon: React.ReactNode; label: string; value: string; color: string; bgColor: string; active?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className={cn("p-3 rounded-xl", bgColor, color, active && "ring-1 ring-white/10")}>
        {icon}
      </div>
      <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider">{label}</span>
      <span className="text-xs font-bold text-white font-mono">{value}</span>
    </div>
  );
}

function FlowArrow({ active, color, reverse }: { active?: boolean; color: string; reverse?: boolean }) {
  const arrowColor = color === 'amber' ? 'text-amber-500/50' : 'text-rose-500/50';
  return (
    <div className={cn("flex items-center gap-0.5", !active && "opacity-20")}>
      {reverse ? (
        <>
          <ChevronRight className={cn("w-3 h-3", arrowColor)} />
          <div className={cn("w-6 h-[1px]", color === 'amber' ? 'bg-amber-500/30' : 'bg-rose-500/30')} />
        </>
      ) : (
        <>
          <div className={cn("w-6 h-[1px]", color === 'amber' ? 'bg-amber-500/30' : 'bg-rose-500/30')} />
          <ChevronRight className={cn("w-3 h-3", arrowColor)} />
        </>
      )}
    </div>
  );
}

function TimelineEvent({ time, label, detail, severity }: {
  time: string; label: string; detail: string; severity: 'live' | 'warning' | 'info' | 'success';
}) {
  const dotColor = severity === 'live' ? 'bg-emerald-400 animate-pulse'
    : severity === 'warning' ? 'bg-amber-400'
    : severity === 'success' ? 'bg-emerald-400'
    : 'bg-indigo-400';

  return (
    <div className="relative flex items-start gap-3">
      <span className={cn("absolute -left-5 top-1.5 w-2 h-2 rounded-full", dotColor)} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 font-mono font-bold">{time}</span>
          <span className="text-xs text-white font-semibold">{label}</span>
        </div>
        <p className="text-[10px] text-slate-500 mt-0.5">{detail}</p>
      </div>
    </div>
  );
}

function BudgetRing({ progress, current, target }: { progress: number; current: number; target: number }) {
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const animatedProgress = useCountUp(Math.min(progress, 100));
  const offset = circumference - (animatedProgress / 100) * circumference;

  const color = animatedProgress > 90 ? '#EF4444' : animatedProgress > 70 ? '#F59E0B' : '#10B981';

  return (
    <div className="relative w-32 h-32">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
        <circle
          cx="60" cy="60" r={radius} fill="none"
          stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
          style={{ filter: `drop-shadow(0 0 10px ${color}30)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-black text-white font-mono">{Math.round(animatedProgress)}%</span>
        <span className="text-[9px] text-slate-500 font-bold mt-0.5">{current} / {target} MAD</span>
      </div>
    </div>
  );
}

function QuickAction({ icon, label, onClick, color }: {
  icon: React.ReactNode; label: string; onClick: () => void; color: string;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.06] hover:border-white/[0.08] hover:translate-y-[-1px] transition-all group"
    >
      <div className={cn("p-2 rounded-lg bg-white/[0.04] group-hover:bg-white/[0.08] transition-colors", color)}>
        {icon}
      </div>
      <span className="text-[10px] text-slate-400 font-bold group-hover:text-white transition-colors">{label}</span>
    </button>
  );
}
