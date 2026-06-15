'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useI18n } from '@/lib/i18n';
import { useAuth } from '@/lib/auth';
import { analyticsApi } from '@/lib/api';
import { formatTimeAgo, cn } from '@/lib/utils';
import {
  BarChart3,
  TrendingUp,
  Bell,
  Zap,
  ArrowUpRight,
  ArrowRight,
  Activity,
  Clock,
  LineChart as LucideLineChart,
  Target,
  Loader2,
  ShieldAlert,
  Cpu,
  Thermometer,
  Flame,
  PlayCircle
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

interface TelemetryFrame {
  timestamp: string;
  gap: number;      // active power (kW)
  grp: number;      // reactive power (kW)
  voltage: number;  // (V)
  intensity: number;// (A)
  sub_metering_1: number; // Kitchen (Wh)
  sub_metering_2: number; // Laundry (Wh)
  sub_metering_3: number; // HVAC (Wh)
  predictions?: number[]; // Added predictions list
}

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

const modelDisplayNames: Record<string, string> = {
  patchtst: 'PatchTST',
  sota: 'SOTA Hybrid',
  cnn_bilstm: 'CNN-BiLSTM',
};

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
  const { t, language } = useI18n();
  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState<'telemetry' | 'overview'>('telemetry');
  
  // Historical / Overview data
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Settings data
  const [systemSettings, setSystemSettings] = useState<any>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/settings')
      .then(res => res.json())
      .then(data => setSystemSettings(data))
      .catch(console.error);
  }, []);

  // Live Telemetry data
  const [liveData, setLiveData] = useState<TelemetryFrame | null>(null);
  const [history, setHistory] = useState<TelemetryFrame[]>([]);
  const [connected, setConnected] = useState(false);
  const [framesLog, setFramesLog] = useState<string[]>([]);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Load analytics & establish WebSockets connection on mount
  useEffect(() => {
    setMounted(true);
    
    // Fetch summary stats
    analyticsApi
      .getSummary()
      .then((data) => setAnalytics(data as unknown as AnalyticsData))
      .catch(() => {
        setAnalytics(null);
      })
      .finally(() => setLoading(false));

    // Resolve websocket URL
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsProto = apiBase.startsWith('https') ? 'wss' : 'ws';
    const host = apiBase.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProto}://${host}/api/v1/forecast/smart-meter/live-ws`;

    console.log(`[DASHBOARD-TELEMETRY] Connecting to ${wsUrl}`);
    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;

    const connect = () => {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnected(true);
        setFramesLog((prev) => [...prev, `[SYSTEM] Connection established to Linky Telemetry stream.`].slice(-50));
      };

      ws.onmessage = (event) => {
        try {
          const frame: TelemetryFrame = JSON.parse(event.data);
          setLiveData(frame);
          
          // Add to rolling history (keep last 20 frames)
          setHistory((prev) => {
            const updated = [...prev, frame];
            if (updated.length > 20) {
              return updated.slice(updated.length - 20);
            }
            return updated;
          });

          // Add to log
          const timeStr = new Date(frame.timestamp).toLocaleTimeString();
          const logMsg = `[${timeStr}] RECV: GAP=${frame.gap}kW | VOLT=${frame.voltage}V | AMP=${frame.intensity}A | SUB3=${frame.sub_metering_3}Wh`;
          setFramesLog((prev) => [...prev, logMsg].slice(-50));
        } catch (err) {
          console.error('[DASHBOARD-TELEMETRY-WS] Error parsing frame:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('[DASHBOARD-TELEMETRY-WS] error:', err);
        setConnected(false);
      };

      ws.onclose = () => {
        setConnected(false);
        setFramesLog((prev) => [...prev, `[SYSTEM] Connection lost. Attempting to reconnect...`].slice(-50));
        reconnectTimer = setTimeout(connect, 4000);
      };
    };

    connect();

    return () => {
      if (ws) ws.close();
      clearTimeout(reconnectTimer);
    };
  }, []);

  // Auto scroll telemetry logs
  useEffect(() => {
    if (activeTab === 'telemetry' && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [framesLog, activeTab]);

  // Calculations for dynamic tariffs based on system settings
  const getTariffInfo = () => {
    const currentHour = new Date().getHours();
    const peakStart = systemSettings?.peak_start_hour ?? 6;
    const peakEnd = systemSettings?.peak_end_hour ?? 22;
    const isPeak = peakStart < peakEnd 
      ? currentHour >= peakStart && currentHour < peakEnd
      : currentHour >= peakStart || currentHour < peakEnd;
    const isOffPeak = !isPeak;
    
    const rate = isOffPeak ? (systemSettings?.off_peak_rate ?? 0.8) : (systemSettings?.peak_rate ?? 1.1);
    const label = isOffPeak 
      ? (language === 'ar' ? 'ساعات خارج الذروة Creuses' : language === 'fr' ? 'Heures Creuses' : 'Off-Peak Hours')
      : (language === 'ar' ? 'ساعات الذروة Pleines' : language === 'fr' ? 'Heures Pleines' : 'Peak Hours');
    return { rate, label, isOffPeak };
  };

  const tariff = getTariffInfo();
  const activePower = liveData?.gap || 0;
  
  // Cost calculations
  const costPerHour = activePower * tariff.rate;
  
  // Calculate projected daily cost dynamically by summing predicted values for the next 24 hours
  // and multiplying them by hourly EDF peak/off-peak tariff rates.
  const calculateProjectedDailyCost = () => {
    if (liveData?.predictions && liveData.predictions.length === 24) {
      let totalCost = 0;
      const startHour = new Date().getHours();
      
      const peakStart = systemSettings?.peak_start_hour ?? 6;
      const peakEnd = systemSettings?.peak_end_hour ?? 22;
      const peakRate = systemSettings?.peak_rate ?? 1.1;
      const offPeakRate = systemSettings?.off_peak_rate ?? 0.8;
      
      liveData.predictions.forEach((predKw, idx) => {
        const hour = (startHour + idx + 1) % 24;
        const isPeak = peakStart < peakEnd 
          ? hour >= peakStart && hour < peakEnd
          : hour >= peakStart || hour < peakEnd;
        const rate = isPeak ? peakRate : offPeakRate;
        totalCost += predKw * rate;
      });
      return totalCost;
    }
    // Fallback: use current cost scaled dynamically but realistically
    return 1.15 * tariff.rate * 24;
  };

  const projectedDailyCost = calculateProjectedDailyCost();
  const projectedMonthlyCost = projectedDailyCost * 30.5;

  // Power Factor cos phi
  const calculatePowerFactor = () => {
    if (!liveData) return 0.95;
    const { gap, grp } = liveData;
    if (gap === 0) return 1.0;
    const s = Math.sqrt(gap * gap + grp * grp);
    return Math.min(1.0, gap / s);
  };

  const powerFactor = calculatePowerFactor();

  // Scrolling chart data mapping: past actual consumption + future predicted consumption
  const buildChartData = () => {
    // 1. Map past telemetry entries
    const dataPoints: Array<{ time: string, consumption: number | null, predicted: number | null }> = history.map((h) => ({
      time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      consumption: h.gap,
      predicted: null,
    }));

    // 2. Append future predictions if available
    const lastFrame = history[history.length - 1];
    if (lastFrame && lastFrame.predictions && lastFrame.predictions.length > 0) {
      // Bridge coordinate at H0: connect actual line to predicted line seamlessly
      if (dataPoints.length > 0) {
        dataPoints[dataPoints.length - 1].predicted = lastFrame.gap;
      }
      
      const lastTime = new Date(lastFrame.timestamp);
      lastFrame.predictions.forEach((p, idx) => {
        const futureTime = new Date(lastTime.getTime() + (idx + 1) * 3600 * 1000);
        dataPoints.push({
          time: futureTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          consumption: null as number | null,
          predicted: p,
        });
      });
    }
    return dataPoints;
  };

  const chartData = buildChartData();

  // AI Insights
  const getSmartAdvice = () => {
    if (activePower > 4.2) {
      return {
        type: 'critical',
        text: language === 'ar' 
          ? 'تنبيه: الاستهلاك مرتفع جداً! يوصى بإيقاف تشغيل الأجهزة غير الضرورية لتجنب التحميل الزائد.' 
          : language === 'fr' 
          ? 'ALERTE: Consommation élevée! Arrêtez les appareils non prioritaires pour soulager le réseau.' 
          : 'CRITICAL ALERT: Very high load! Recommend turning off non-priority devices immediately.'
      };
    } else if (activePower > 2.5 && !tariff.isOffPeak) {
      return {
        type: 'warning',
        text: language === 'ar'
          ? 'توصية: يرجى ترحيل استخدام أجهزة الغسيل والتسخين الكبيرة إلى الساعاتCreuses لتوفير التكاليف.'
          : language === 'fr'
          ? 'CONSEIL: Décalez l\'utilisation du lave-linge/ballon d\'eau chaude en Heures Creuses.'
          : 'ADVICE: Shift laundry/heating loads to Off-Peak hours to save on electricity tariffs.'
      };
    } else {
      return {
        type: 'optimal',
        text: language === 'ar'
          ? 'الحالة: استهلاك مستقر ومثالي للشبكة. الأتمتة تعمل بكفاءة.'
          : language === 'fr'
          ? 'STATUT: Consommation stable. Optimisation énergétique active.'
          : 'STATUS: Consumption levels are optimal. Smart energy system operating normally.'
      };
    }
  };

  const advice = getSmartAdvice();

  const getGreetingText = () => {
    const hour = new Date().getHours();
    if (language === 'ar') {
      if (hour < 12) return 'صباح الخير';
      return 'مساء الخير';
    }
    if (language === 'fr') {
      if (hour < 12) return 'Bonjour';
      return 'Bonsoir';
    }
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  // Compute overview stat cards
  const bestModel = analytics?.models_used
    ? Object.entries(analytics.models_used).sort((a, b) => b[1] - a[1])[0]
    : null;

  const statCards = [
    {
      title: t('dashboard.forecasts_run'),
      value: analytics ? analytics.total_forecasts.toString() : '—',
      change: bestModel ? `Top: ${modelDisplayNames[bestModel[0]] || bestModel[0]}` : '',
      changeType: 'positive' as const,
      icon: BarChart3,
      gradient: 'from-blue-500 to-blue-600',
      glow: 'glow-blue',
    },
    {
      title: t('dashboard.total_consumption'),
      value: analytics?.avg_peak_power
        ? `${analytics.avg_peak_power.toFixed(2)} kW`
        : '—',
      change: language === 'ar' ? 'متوسط حمل الطاقة' : language === 'fr' ? 'Puissance moyenne' : 'Avg Peak Power',
      changeType: 'positive' as const,
      icon: Target,
      gradient: 'from-emerald-500 to-emerald-600',
      glow: 'glow-emerald',
    },
    {
      title: t('alerts.active_alerts'),
      value: analytics ? analytics.unacknowledged_alerts.toString() : '—',
      change: analytics ? `${analytics.total_alerts} total` : '',
      changeType: 'negative' as const,
      icon: Bell,
      gradient: 'from-amber-500 to-orange-500',
      glow: '',
    },
    {
      title: language === 'ar' ? 'النماذج المستعملة' : language === 'fr' ? 'Modèles Utilisés' : 'Models Used',
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

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Welcome Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              {getGreetingText()},{' '}
              <span className="gradient-text">
                {user?.full_name?.split(' ')[0] || 'User'}
              </span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              {activeTab === 'telemetry' 
                ? (language === 'ar' ? 'مراقبة فورية وتحليل استهلاك الطاقة المباشر للعداد الذكي' : language === 'fr' ? 'Flux en temps réel de votre compteur Linky (API simulée).' : 'Real-time telemetry stream from your Enedis Linky utility meter.')
                : t('dashboard.subtitle')}
            </p>
          </div>

          {/* Glassmorphism Tab Switcher */}
          <div className="flex p-0.5 bg-white/[0.03] border border-white/[0.06] rounded-xl self-start">
            <button
              id="tab-telemetry"
              onClick={() => setActiveTab('telemetry')}
              className={cn(
                "flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all duration-200 cursor-pointer",
                activeTab === 'telemetry'
                  ? "bg-blue-500/15 text-blue-400 border border-blue-500/20"
                  : "text-slate-400 hover:text-slate-200 border border-transparent"
              )}
            >
              <Zap className="w-3.5 h-3.5" />
              {language === 'ar' ? 'القياس المباشر' : language === 'fr' ? 'Télémesures Live' : 'Live Smart Meter'}
            </button>
            <button
              id="tab-overview"
              onClick={() => setActiveTab('overview')}
              className={cn(
                "flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all duration-200 cursor-pointer",
                activeTab === 'overview'
                  ? "bg-blue-500/15 text-blue-400 border border-blue-500/20"
                  : "text-slate-400 hover:text-slate-200 border border-transparent"
              )}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              {language === 'ar' ? 'نظرة عامة على النظام' : language === 'fr' ? 'Vue globale' : 'System Overview'}
            </button>
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* VIEW 1: LIVE TELEMETRY DASHBOARD */}
        {/* ------------------------------------------------------------- */}
        {activeTab === 'telemetry' && (
          <div className="space-y-6 animate-in fade-in duration-300">
            {/* Live Connection & AI Automation Advice */}
            <Card className={cn(
              "border-l-4 border-white/[0.06] transition-all duration-300",
              advice.type === 'critical' ? 'border-red-500 bg-red-950/20' : 
              advice.type === 'warning' ? 'border-amber-500 bg-amber-950/20' : 
              'border-emerald-500 bg-emerald-950/20'
            )}>
              <CardContent className="p-4 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <ShieldAlert className={cn(
                    "w-5 h-5 shrink-0 mt-0.5 animate-pulse",
                    advice.type === 'critical' ? 'text-red-400' : 
                    advice.type === 'warning' ? 'text-amber-400' : 
                    'text-emerald-400'
                  )} />
                  <div>
                    <p className="text-xs font-bold text-white uppercase tracking-wider">
                      {language === 'ar' ? 'توصيات الذكاء الاصطناعي والأتمتة' : language === 'fr' ? 'Recommandations IA & Automatisation' : 'AI Automation Insights'}
                    </p>
                    <p className="text-sm text-slate-300 mt-1">
                      {advice.text}
                    </p>
                  </div>
                </div>
                <Badge className={cn(
                  "shrink-0 uppercase font-mono tracking-wider text-[9px] px-2 py-0.5",
                  connected ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
                )}>
                  <span className={cn("w-1.5 h-1.5 rounded-full inline-block mr-1.5", connected ? "bg-emerald-400 animate-ping" : "bg-red-500")} />
                  {connected ? 'LINKY ONLINE' : 'LINKY OFFLINE'}
                </Badge>
              </CardContent>
            </Card>

            {/* Core Metrics Gauges */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Active Power Gauge */}
              <Card className="glass-card border-white/[0.06] overflow-hidden relative">
                <CardContent className="p-5 flex flex-col items-center justify-center text-center">
                  <div className="relative w-28 h-28 flex items-center justify-center rounded-full border-4 border-dashed border-white/5">
                    {/* Glowing ring */}
                    <div className={cn(
                      "absolute inset-0 rounded-full border-4 transition-all duration-500",
                      activePower > 4.0 ? 'border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.2)]' :
                      activePower > 2.2 ? 'border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.2)]' :
                      'border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                    )} />
                    <div className="z-10">
                      <p className="text-2xl font-black text-white font-mono">{activePower ? activePower.toFixed(3) : '0.000'}</p>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">kW</p>
                    </div>
                  </div>
                  <p className="text-xs font-semibold text-white mt-4 uppercase tracking-wider">
                    {language === 'ar' ? 'الحمل النشط الفوري' : language === 'fr' ? 'Puissance Active' : 'Current Active Power'}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-1">Simulated Linky GAP</p>
                </CardContent>
              </Card>

              {/* Voltage Card */}
              <Card className="glass-card border-white/[0.06] flex items-center justify-between p-5">
                <div className="space-y-2">
                  <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                    {language === 'ar' ? 'الجهد الكهربائي' : language === 'fr' ? 'Tension' : 'Voltage'}
                  </p>
                  <p className="text-2xl font-bold text-white font-mono">
                    {liveData ? `${liveData.voltage} V` : '—'}
                  </p>
                  <Badge variant="outline" className="border-blue-500/20 text-blue-400 bg-blue-500/10 text-[9px] font-mono">
                    Safe range: 220V-240V
                  </Badge>
                </div>
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center shrink-0">
                  <Cpu className="w-5 h-5 text-blue-400" />
                </div>
              </Card>

              {/* Current draw Card */}
              <Card className="glass-card border-white/[0.06] flex items-center justify-between p-5">
                <div className="space-y-2">
                  <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                    {language === 'ar' ? 'التيار الإجمالي' : language === 'fr' ? 'Intensité' : 'Current draw'}
                  </p>
                  <p className="text-2xl font-bold text-white font-mono">
                    {liveData ? `${liveData.intensity} A` : '—'}
                  </p>
                  <p className="text-[10px] text-slate-500">Live Grid Current Intensity</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center shrink-0">
                  <Activity className="w-5 h-5 text-purple-400" />
                </div>
              </Card>

              {/* Power Factor Card */}
              <Card className="glass-card border-white/[0.06] flex items-center justify-between p-5">
                <div className="space-y-2">
                  <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                    {language === 'ar' ? 'معامل القدرة' : language === 'fr' ? 'Facteur de Puissance' : 'Power Factor'}
                  </p>
                  <p className="text-2xl font-bold text-white font-mono">
                    {powerFactor.toFixed(3)}
                  </p>
                  <Badge variant="outline" className="border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[9px] font-mono">
                    cos φ (optimal &gt; 0.90)
                  </Badge>
                </div>
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center shrink-0">
                  <Zap className="w-5 h-5 text-cyan-400" />
                </div>
              </Card>
            </div>

            {/* Live Chart & Cost Estimation Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Scrolling Recharts Curve */}
              <Card className="glass-card border-white/[0.06] lg:col-span-2">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-semibold text-white flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                      {language === 'ar' ? 'منحنى الاستهلاك المباشر' : language === 'fr' ? 'Graphique en Temps Réel' : 'Live Consumption Curve'}
                    </span>
                    <span className="text-xs font-normal text-slate-400">
                      {language === 'ar' ? 'تحديث تلقائي كل ثانيتين' : language === 'fr' ? 'Mise à jour 2s' : 'Auto-updates every 2s'}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="h-[280px] mt-2">
                    {history.length < 2 ? (
                      <div className="w-full h-full flex flex-col items-center justify-center gap-2">
                        <Loader2 className="w-7 h-7 text-slate-600 animate-spin" />
                        <p className="text-xs text-slate-400">Connecting and collecting Linky stream frames...</p>
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(16,185,129,0.06)" vertical={false} />
                          <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 10 }} />
                          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} domain={[0, 'auto']} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#111827',
                              border: '1px solid rgba(16,185,129,0.15)',
                              borderRadius: '12px',
                              color: '#E2E8F0',
                              fontSize: '11px',
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="consumption"
                            stroke="#10B981"
                            strokeWidth={3}
                            dot={false}
                            activeDot={{ r: 6, fill: '#10B981', stroke: '#111827', strokeWidth: 2 }}
                          />
                          <Line
                            type="monotone"
                            dataKey="predicted"
                            stroke="#06B6D4"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                            activeDot={{ r: 5, fill: '#06B6D4', stroke: '#111827', strokeWidth: 2 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Financial Estimates */}
              <Card className="glass-card border-white/[0.06]">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold text-white flex items-center justify-between">
                    <span>{language === 'ar' ? 'تقدير التكاليف الفورية' : language === 'fr' ? 'Estimation Financière' : 'Live Cost Estimation'}</span>
                    <Badge variant="outline" className={tariff.isOffPeak ? "border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[9px]" : "border-amber-500/20 text-amber-400 bg-amber-500/10 text-[9px]"}>
                      {tariff.label}
                    </Badge>
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400">
                    {systemSettings?.electricity_provider || 'Provider'} Tarif: {systemSettings?.currency || 'MAD'} {tariff.rate}/kWh
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Cost/Hour */}
                  <div className="p-3.5 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80">
                    <p className="text-[10px] text-slate-500 font-bold uppercase">{language === 'ar' ? 'التكلفة في الساعة' : language === 'fr' ? 'Coût Horaire' : 'Cost Per Hour'}</p>
                    <p className="text-xl font-bold text-white mt-1 font-mono">{systemSettings?.currency || 'MAD'} {costPerHour.toFixed(4)}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Based on active power: {activePower.toFixed(3)} kW</p>
                  </div>

                  {/* Projected Day */}
                  <div className="p-3.5 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80">
                    <p className="text-[10px] text-slate-500 font-bold uppercase">{language === 'ar' ? 'التكلفة اليومية المتوقعة' : language === 'fr' ? 'Projection Journalière' : 'Projected Daily Cost'}</p>
                    <p className="text-xl font-bold text-emerald-400 mt-1 font-mono">{systemSettings?.currency || 'MAD'} {projectedDailyCost.toFixed(2)}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">If current usage holds for 24 hours</p>
                  </div>

                  {/* Projected Month */}
                  <div className="p-3.5 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80">
                    <p className="text-[10px] text-slate-500 font-bold uppercase">{language === 'ar' ? 'التكلفة الشهرية المتوقعة' : language === 'fr' ? 'Projection Mensuelle' : 'Projected Monthly Cost'}</p>
                    <p className="text-xl font-black text-cyan-400 mt-1 font-mono">{systemSettings?.currency || 'MAD'} {projectedMonthlyCost.toFixed(2)}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Projected billing cycle forecast</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Appliance Breakdown & Raw Logs */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Appliance Load distribution */}
              <Card className="glass-card border-white/[0.06] lg:col-span-2">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold text-white">
                    {language === 'ar' ? 'تفكيك أحمال الأجهزة الحية' : language === 'fr' ? 'Distribution des Charges (Sub-metering)' : 'Real-time Appliance Load Distribution'}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* kitchen sub1 */}
                  <div>
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-slate-300 font-medium flex items-center gap-1.5">
                        <Flame className="w-3.5 h-3.5 text-amber-500" />
                        Kitchen (Sub-metering 1)
                      </span>
                      <span className="text-slate-400 font-mono">{liveData ? `${liveData.sub_metering_1} Wh` : '—'}</span>
                    </div>
                    <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all duration-500"
                        style={{ width: `${Math.min(100, (liveData?.sub_metering_1 || 0) / 15)}%` }}
                      />
                    </div>
                  </div>

                  {/* laundry sub2 */}
                  <div>
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-slate-300 font-medium flex items-center gap-1.5">
                        <Zap className="w-3.5 h-3.5 text-purple-400" />
                        Laundry & Cleaning (Sub-metering 2)
                      </span>
                      <span className="text-slate-400 font-mono">{liveData ? `${liveData.sub_metering_2} Wh` : '—'}</span>
                    </div>
                    <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500"
                        style={{ width: `${Math.min(100, (liveData?.sub_metering_2 || 0) / 15)}%` }}
                      />
                    </div>
                  </div>

                  {/* hvac sub3 */}
                  <div>
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-slate-300 font-medium flex items-center gap-1.5">
                        <Thermometer className="w-3.5 h-3.5 text-blue-400" />
                        HVAC & Hot Water (Sub-metering 3)
                      </span>
                      <span className="text-slate-400 font-mono">{liveData ? `${liveData.sub_metering_3} Wh` : '—'}</span>
                    </div>
                    <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
                        style={{ width: `${Math.min(100, (liveData?.sub_metering_3 || 0) / 40)}%` }}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Raw logger */}
              <Card className="glass-card border-white/[0.06] flex flex-col h-[230px]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                    <PlayCircle className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                    Raw Linky Telemetry Log
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 overflow-hidden p-3 pt-0">
                  <div ref={logContainerRef} className="w-full h-full rounded-xl bg-black/60 border border-white/5 p-3 font-mono text-[9px] text-slate-400 overflow-y-auto space-y-1">
                    {framesLog.map((log, i) => (
                      <p key={i} className={log.includes('[SYSTEM]') ? 'text-emerald-400' : 'text-slate-400'}>
                        {log}
                      </p>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* VIEW 2: SYSTEM OVERVIEW (OLD DASHBOARD CONTENT) */}
        {/* ------------------------------------------------------------- */}
        {activeTab === 'overview' && (
          <div className="space-y-6 animate-in fade-in duration-300">
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
                        <p className="text-2xl font-bold text-white font-mono">
                          {loading ? (
                            <Loader2 className="w-5 h-5 animate-spin text-slate-500" />
                          ) : (
                            card.value
                          )}
                        </p>
                        <div className="flex items-center gap-1">
                          <span
                            className={cn(
                              "text-xs font-medium",
                              card.changeType === 'positive' ? 'text-emerald-400' : 'text-amber-400'
                            )}
                          >
                            {card.change}
                          </span>
                        </div>
                      </div>
                      <div
                        className={cn(
                          "flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br shadow-lg shrink-0",
                          card.gradient
                        )}
                      >
                        <card.icon className="w-5 h-5 text-white" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Consumption Forecast Chart & Quick Actions */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Consumption Area Chart */}
              <Card className="glass-card border-white/[0.06] lg:col-span-2">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                      <Activity className="w-4 h-4 text-blue-400" />
                      {t('dashboard.consumption_forecast')}
                      {(!analytics || !analytics.consumption_trend || analytics.consumption_trend.length === 0) && (
                        <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500/20 bg-amber-500/10 ml-2">
                          {language === 'ar' ? 'بيانات توضيحية' : language === 'fr' ? 'Données Démo' : 'Demo Data'}
                        </Badge>
                      )}
                    </CardTitle>
                    <div className="flex items-center gap-4 text-xs">
                      <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        <span className="text-slate-400">{language === 'ar' ? 'حقيقي' : language === 'fr' ? 'Réel' : 'Actual'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-cyan-400" />
                        <span className="text-slate-400">{language === 'ar' ? 'متوقع' : language === 'fr' ? 'Prédit' : 'Predicted'}</span>
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
                    {language === 'ar' ? 'إجراءات سريعة' : language === 'fr' ? 'Actions Rapides' : 'Quick Actions'}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <button
                    id="quick-action-forecast"
                    onClick={() => router.push('/forecast')}
                    className="w-full flex items-center gap-3 p-3 rounded-xl bg-blue-500/10 border border-blue-500/10 hover:border-blue-500/20 hover:bg-blue-500/15 transition-all duration-200 group cursor-pointer"
                  >
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-blue-500/20 shrink-0">
                      <LucideLineChart className="w-4 h-4 text-blue-400" />
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {t('forecast.run_forecast')}
                      </p>
                      <p className="text-xs text-slate-400 truncate">
                        {language === 'ar' ? 'توقع استهلاك الطاقة' : language === 'fr' ? 'Prédire la consommation' : 'Predict energy consumption'}
                      </p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-blue-400 transition-colors shrink-0" />
                  </button>

                  <button
                    id="quick-action-compare"
                    onClick={() => router.push('/forecast')}
                    className="w-full flex items-center gap-3 p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/10 hover:border-cyan-500/20 hover:bg-cyan-500/15 transition-all duration-200 group cursor-pointer"
                  >
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-cyan-500/20 shrink-0">
                      <TrendingUp className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {language === 'ar' ? 'مقارنة النماذج' : language === 'fr' ? 'Comparer les Modèles' : 'Compare Models'}
                      </p>
                      <p className="text-xs text-slate-400 truncate">
                        {language === 'ar' ? 'مقارنة ثلاثية للنماذج' : language === 'fr' ? 'Comparaison de 3 modèles' : '3-way model comparison'}
                      </p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors shrink-0" />
                  </button>

                  <button
                    id="quick-action-analytics"
                    onClick={() => router.push('/analytics')}
                    className="w-full flex items-center gap-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/10 hover:border-emerald-500/20 hover:bg-emerald-500/15 transition-all duration-200 group cursor-pointer"
                  >
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-emerald-500/20 shrink-0">
                      <BarChart3 className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {t('nav.analytics')}
                      </p>
                      <p className="text-xs text-slate-400 truncate">
                        {language === 'ar' ? 'استكشاف الأنماط والاتجاهات' : language === 'fr' ? 'Explorer les tendances' : 'Explore insights & trends'}
                      </p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 transition-colors shrink-0" />
                  </button>

                  <button
                    id="quick-action-alerts"
                    onClick={() => router.push('/alerts')}
                    className="w-full flex items-center gap-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/10 hover:border-amber-500/20 hover:bg-amber-500/15 transition-all duration-200 group cursor-pointer"
                  >
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-amber-500/20 shrink-0">
                      <Bell className="w-4 h-4 text-amber-400" />
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {language === 'ar' ? 'إدارة التنبيهات' : language === 'fr' ? 'Gérer les Alertes' : 'Manage Alerts'}
                      </p>
                      <p className="text-xs text-slate-400 truncate">
                        {analytics
                          ? `${analytics.unacknowledged_alerts} ${language === 'ar' ? 'تنبيهات نشطة' : language === 'fr' ? 'alertes actives' : 'active alerts'}`
                          : t('nav.alerts')}
                      </p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-amber-400 transition-colors shrink-0" />
                  </button>
                </CardContent>
              </Card>
            </div>

            {/* Recent Forecast Activity */}
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                    <Clock className="w-4 h-4 text-blue-400" />
                    {t('dashboard.recent_activity')}
                  </CardTitle>
                  <Button
                    id="dashboard-view-all"
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push('/forecast')}
                    className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                  >
                    {language === 'ar' ? 'عرض الكل' : language === 'fr' ? 'Voir Tout' : 'View All'}
                    <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {loading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
                    </div>
                  ) : analytics?.recent_forecasts && analytics.recent_forecasts.length > 0 ? (
                    analytics.recent_forecasts.map((forecast) => (
                      <div
                        key={forecast.id}
                        id={`forecast-item-${forecast.id}`}
                        className="flex items-center justify-between p-3 rounded-xl hover:bg-white/[0.02] transition-all duration-200"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-blue-500/10 shrink-0">
                            <LucideLineChart className="w-4 h-4 text-blue-400" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-white truncate">
                              {modelDisplayNames[forecast.model_name] || forecast.model_name}
                            </p>
                            <p className="text-xs text-slate-500">
                              {formatTimeAgo(forecast.created_at)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <div className="text-right">
                            <p className="text-sm font-medium text-emerald-400 font-mono">
                              {forecast.peak_power
                                ? `${forecast.peak_power.toFixed(2)} kW`
                                : '—'}
                            </p>
                            <p className="text-[10px] text-slate-500 uppercase">
                              {language === 'ar' ? 'حمل الذروة' : language === 'fr' ? 'puissance max' : 'peak power'}
                            </p>
                          </div>
                          <Badge
                            variant="outline"
                            className="border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[10px]"
                          >
                            {language === 'ar' ? 'مكتمل' : language === 'fr' ? 'terminé' : 'completed'}
                          </Badge>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-sm text-slate-400">
                        {t('dashboard.no_forecasts')}
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
