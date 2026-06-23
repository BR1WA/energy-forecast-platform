'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useI18n } from '@/lib/i18n';
import { useAuth } from '@/lib/auth';
import { can, Feature } from '@/lib/entitlements';
import { analyticsApi, settingsApi, forecastApi, getAccessToken } from '@/lib/api';
import { EnergyBudget } from '@/types';
import { toast } from 'sonner';
import { useWebSocket } from '@/hooks/useWebSocket';
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
  PlayCircle,
  Lock
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

// Removed unused overview definitions

export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { t, language } = useI18n();
  const [mounted, setMounted] = useState(false);
  // Settings data
  const [systemSettings, setSystemSettings] = useState<any>(null);

  useEffect(() => {
    settingsApi
      .getSettings()
      .then(data => setSystemSettings(data))
      .catch(console.error);
  }, []);

  // Live Telemetry data
  const [liveData, setLiveData] = useState<TelemetryFrame | null>(null);
  const [history, setHistory] = useState<TelemetryFrame[]>([]);
  const [historyWindow, setHistoryWindow] = useState<number>(20);
  const [framesLog, setFramesLog] = useState<string[]>([]);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Forecast/Timeframe state for Day, Week, Month
  const [dashboardTimeframe, setDashboardTimeframe] = useState<'live' | '24' | '168' | '720'>('live');
  const [forecastChartData, setForecastChartData] = useState<any[] | null>(null);
  const [isLoadingForecast, setIsLoadingForecast] = useState<boolean>(false);

  // Budget progress state
  const [budget, setBudget] = useState<EnergyBudget | null>(null);
  const [isEditingBudget, setIsEditingBudget] = useState(false);
  const [budgetValue, setBudgetValue] = useState('');
  const [isSavingBudget, setIsSavingBudget] = useState(false);

  // Load analytics, budget & establish WebSockets connection on mount
  useEffect(() => {
    setMounted(true);
    
    // Fetch summary stats
    // Fetch summary stats removed (now in analytics page)

    // Fetch budget
    settingsApi
      .getBudget()
      .then((data) => {
        setBudget(data);
        if (data) {
          setBudgetValue(data.monthly_budget_mad.toString());
        }
      })
      .catch(console.error);
  }, []);

  const [wsUrl, setWsUrl] = useState<string | null>(null);

  useEffect(() => {
    if (mounted) {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const wsProto = apiBase.startsWith('https') ? 'wss' : 'ws';
      const host = apiBase.replace(/^https?:\/\//, '');
      const token = getAccessToken();
      setWsUrl(`${wsProto}://${host}/api/v1/forecast/smart-meter/live-ws${token ? `?token=${encodeURIComponent(token)}` : ''}`);
    }
  }, [mounted]);

  const { connected, reconnectAttempt } = useWebSocket(wsUrl, {
    onOpen: () => {
      setFramesLog((prev) => [...prev, `[SYSTEM] Connection established to Linky Telemetry stream.`].slice(-50));
    },
    onMessage: (event) => {
      try {
        const frame: TelemetryFrame = JSON.parse(event.data);
        setLiveData(frame);
        
        // Add to rolling history (keep last 500 frames in memory)
        setHistory((prev) => {
          const updated = [...prev, frame];
          if (updated.length > 500) {
            return updated.slice(updated.length - 500);
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
    },
  });

  // Reconnecting log effect
  useEffect(() => {
    if (reconnectAttempt > 0 && !connected) {
      setFramesLog((prev) => [
        ...prev,
        `[SYSTEM] Connection lost. Attempting to reconnect (attempt ${reconnectAttempt})...`
      ].slice(-50));
    }
  }, [reconnectAttempt, connected]);

  // Auto scroll telemetry logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [framesLog]);

  // Calculations for dynamic tariffs based on Moroccan National Tiered Pricing (ONEE)
  const getTariffInfo = () => {
    // 1. Calculate projected monthly consumption in kWh
    // Daily active consumption is approximately (activePower * 24)
    // Monthly consumption is (daily consumption * 30.5)
    const projectedDailyKwh = liveData?.predictions 
      ? liveData.predictions.reduce((a, b) => a + b, 0) 
      : (liveData?.gap || 2.8) * 24;
    const projectedMonthlyKwh = projectedDailyKwh * 30.5;

    let rate = 0.9010;
    let label = "";
    
    if (projectedMonthlyKwh <= 150) {
      // Progressive Billing
      if (projectedMonthlyKwh <= 100) {
        rate = 0.9010;
        label = language === 'ar' ? 'الشطر 1 (تدريجي)' : language === 'fr' ? 'Tranche 1 (Progressive)' : 'Tranche 1 (Progressive)';
      } else {
        const cost = (100 * 0.9010) + ((projectedMonthlyKwh - 100) * 1.0735);
        rate = cost / projectedMonthlyKwh;
        label = language === 'ar' ? 'الشطر 2 (تدريجي)' : language === 'fr' ? 'Tranche 2 (Progressive)' : 'Tranche 2 (Progressive)';
      }
    } else {
      // Selective Billing
      if (projectedMonthlyKwh <= 200) {
        rate = 1.0735;
        label = language === 'ar' ? 'الشطر 3 (انتقائي)' : language === 'fr' ? 'Tranche 3 (Sélective)' : 'Tranche 3 (Selective)';
      } else if (projectedMonthlyKwh <= 300) {
        rate = 1.1601;
        label = language === 'ar' ? 'الشطر 4 (انتقائي)' : language === 'fr' ? 'Tranche 4 (Sélective)' : 'Tranche 4 (Selective)';
      } else if (projectedMonthlyKwh <= 500) {
        rate = 1.3817;
        label = language === 'ar' ? 'الشطر 5 (انتقائي)' : language === 'fr' ? 'Tranche 5 (Sélective)' : 'Tranche 5 (Selective)';
      } else {
        rate = 1.5958;
        label = language === 'ar' ? 'الشطر 6 (انتقائي)' : language === 'fr' ? 'Tranche 6 (Sélective)' : 'Tranche 6 (Selective)';
      }
    }

    return { rate, label, isOffPeak: false };
  };

  const tariff = getTariffInfo();
  const activePower = liveData?.gap || 0;
  
  // Cost calculations
  const costPerHour = activePower * tariff.rate;
  
  // Calculate projected daily cost dynamically by summing predicted values for the next 24 hours
  // and multiplying them by the Moroccan ONEE tariff rate.
  const calculateProjectedDailyCost = () => {
    if (liveData?.predictions && liveData.predictions.length === 24) {
      const dailyKwh = liveData.predictions.reduce((a, b) => a + b, 0);
      return dailyKwh * tariff.rate;
    }
    // Fallback: use current cost scaled dynamically
    return activePower * 24 * tariff.rate;
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
    const slicedHistory = historyWindow === 9999 ? history : history.slice(-historyWindow);
    const dataPoints: Array<{ time: string, consumption: number | null, predicted: number | null }> = slicedHistory.map((h) => ({
      time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      consumption: h.gap,
      predicted: null,
    }));

    // 2. Append future predictions if available (Pro/Enterprise only)
    const lastFrame = history[history.length - 1];
    const hasPremiumForecast = can(user, Feature.PRO_FORECAST_CURVE);
    if (hasPremiumForecast && lastFrame && lastFrame.predictions && lastFrame.predictions.length > 0) {
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

  const processDashboardForecastData = (
    horizon: number,
    inputData: any,
    predictions: number[][] | undefined,
    createdAtStr?: string
  ) => {
    const chartDataResult: Array<Record<string, any>> = [];
    const createdDate = createdAtStr ? new Date(createdAtStr) : new Date();
    
    if (!inputData || !Array.isArray(inputData)) return chartDataResult;
    if (!predictions || !Array.isArray(predictions)) return chartDataResult;

    let lookback = 96;
    if (horizon === 168) lookback = 512;
    else if (horizon === 720) lookback = 1440;

    const flatInput: number[] = Array.isArray(inputData[0])
      ? (inputData as number[][]).map(row => row[0])
      : (inputData as number[]);
    const slicedInput = flatInput.slice(-lookback);

    if (horizon === 24) {
      const historyToShow = slicedInput.slice(-24);
      for (let i = 0; i < historyToShow.length; i++) {
        const pointTime = new Date(createdDate.getTime() - (historyToShow.length - i) * 3600 * 1000);
        chartDataResult.push({
          time: pointTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          historical: Number(historyToShow[i].toFixed(3)),
        });
      }

      const bridgePoint: Record<string, any> = {
        time: createdDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        historical: Number(historyToShow[historyToShow.length - 1].toFixed(3)),
        predicted: Number(predictions[0][0].toFixed(3)),
      };
      chartDataResult.push(bridgePoint);

      for (let i = 0; i < predictions.length; i++) {
        const pointTime = new Date(createdDate.getTime() + (i + 1) * 3600 * 1000);
        chartDataResult.push({
          time: pointTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          predicted: Number(predictions[i][0].toFixed(3)),
        });
      }
    } else {
      const historyHours = horizon === 168 ? 168 : 720;
      const historyToShow = slicedInput.slice(-historyHours);
      const numDays = horizon === 168 ? 7 : 30;

      const formatDateLabel = (d: Date) => {
        return d.toLocaleDateString([], { day: '2-digit', month: 'short' });
      };

      for (let d = 0; d < numDays; d++) {
        const daySlice = historyToShow.slice(d * 24, (d + 1) * 24);
        if (daySlice.length === 0) continue;
        const dailySum = daySlice.reduce((a, b) => a + b, 0);
        const dayDate = new Date(createdDate.getTime() - (numDays - d) * 24 * 3600 * 1000);
        chartDataResult.push({
          time: formatDateLabel(dayDate),
          historical: Number(dailySum.toFixed(2)),
        });
      }

      const lastDayHistorySlice = historyToShow.slice(-24);
      const lastDayHistorySum = lastDayHistorySlice.reduce((a, b) => a + b, 0);
      const firstDayPredictSlice = predictions.slice(0, 24);
      const firstDayPredictSum = firstDayPredictSlice.reduce((a, b) => a + b[0], 0);

      chartDataResult.push({
        time: formatDateLabel(createdDate),
        historical: Number(lastDayHistorySum.toFixed(2)),
        predicted: Number(firstDayPredictSum.toFixed(2)),
      });

      for (let d = 0; d < numDays; d++) {
        const dayDate = new Date(createdDate.getTime() + (d + 1) * 24 * 3600 * 1000);
        const dayPredictSlice = predictions.slice(d * 24, (d + 1) * 24);
        if (dayPredictSlice.length === 0) continue;
        const dayPredictSum = dayPredictSlice.reduce((a, b) => a + b[0], 0);
        chartDataResult.push({
          time: formatDateLabel(dayDate),
          predicted: Number(dayPredictSum.toFixed(2)),
        });
      }
    }

    return chartDataResult;
  };

  const getDashboardTickInterval = (dataLength: number, timeframe: string): number => {
    if (timeframe === '24') return 6;
    if (timeframe === '168') return 1;
    if (timeframe === '720') return 5;
    return 6;
  };

  useEffect(() => {
    if (dashboardTimeframe === 'live') {
      setForecastChartData(null);
      return;
    }

    const fetchForecast = async () => {
      setIsLoadingForecast(true);
      try {
        const horizonNum = parseInt(dashboardTimeframe);
        let modelName = 'sota';
        if (horizonNum === 168) {
          modelName = user?.preferences?.default_model_168 || 'itransformer_168';
        } else if (horizonNum === 720) {
          modelName = user?.preferences?.default_model_720 || 'itransformer_720';
        } else {
          modelName = user?.preferences?.default_model_24 || 'sota';
        }

        const result = await forecastApi.predictSmartMeter(modelName, horizonNum);
        const processed = processDashboardForecastData(
          horizonNum,
          result.input_data,
          result.predictions,
          result.created_at
        );
        setForecastChartData(processed);
      } catch (err) {
        console.error("Failed to fetch dashboard forecast:", err);
        toast.error("Failed to fetch forecast for the selected timeframe.");
        setDashboardTimeframe('live');
      } finally {
        setIsLoadingForecast(false);
      }
    };

    fetchForecast();
  }, [dashboardTimeframe]);

  const handleSaveBudget = async () => {
    const val = parseFloat(budgetValue);
    if (isNaN(val) || val <= 0) {
      toast.error("Please enter a valid budget amount.");
      return;
    }
    setIsSavingBudget(true);
    try {
      const updatedBudget = await settingsApi.setBudget({
        monthly_budget_mad: val,
      });
      setBudget(updatedBudget);
      setBudgetValue(updatedBudget.monthly_budget_mad.toString());
      setIsEditingBudget(false);
      toast.success("Monthly budget updated!");
    } catch (err) {
      console.error("Failed to update budget", err);
      toast.error("Failed to update budget. Please try again.");
    } finally {
      setIsSavingBudget(false);
    }
  };

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
              {language === 'ar' ? 'مراقبة فورية وتحليل استهلاك الطاقة المباشر للعداد الذكي' : language === 'fr' ? 'Flux en temps réel de votre compteur Linky (API simulée).' : 'Real-time telemetry stream from your Enedis Linky utility meter.'}
            </p>
          </div>


        </div>

        {/* ------------------------------------------------------------- */}
        {/* LIVE TELEMETRY DASHBOARD */}
        {/* ------------------------------------------------------------- */}
        {true && (
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
                  connected ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : reconnectAttempt > 0 ? "bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse" : "bg-red-500/10 text-red-400 border border-red-500/20"
                )}>
                  <span className={cn("w-1.5 h-1.5 rounded-full inline-block mr-1.5", connected ? "bg-emerald-400 animate-ping" : reconnectAttempt > 0 ? "bg-amber-400 animate-pulse" : "bg-red-500")} />
                  {connected ? 'LINKY ONLINE' : reconnectAttempt > 0 ? `RECONNECTING (${reconnectAttempt})` : 'LINKY OFFLINE'}
                </Badge>
              </CardContent>
            </Card>

            {/* Core Metrics Gauges */}
            <div className={cn(
              "grid gap-4",
              can(user, Feature.PRO_FORECAST_CURVE)
                ? "grid-cols-1 md:grid-cols-2 lg:grid-cols-4"
                : "grid-cols-1 md:grid-cols-2"
            )}>
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
              {can(user, Feature.PRO_FORECAST_CURVE) && (
                <>
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
                </>
              )}
            </div>

            {/* Live Chart & Cost Estimation Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Scrolling Recharts Curve */}
              <Card className="glass-card border-white/[0.06] lg:col-span-2">
                <CardHeader className="pb-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                      {language === 'ar' ? 'منحنى الاستهلاك المباشر' : language === 'fr' ? 'Graphique en Temps Réel' : 'Live Consumption Curve'}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <div className="flex bg-[#111827] border border-white/10 rounded-lg p-0.5 select-none">
                        {[
                          { value: 'live', label: 'Live' },
                          { value: '24', label: 'Day' },
                          { value: '168', label: 'Week' },
                          { value: '720', label: 'Month' },
                        ].map((opt) => (
                          <button
                            key={opt.value}
                            onClick={() => setDashboardTimeframe(opt.value as any)}
                            className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all duration-200 ${
                              dashboardTimeframe === opt.value
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'text-slate-400 hover:text-white border border-transparent'
                            }`}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                      <span className="text-[10px] text-slate-500 hidden md:inline">
                        {dashboardTimeframe === 'live' ? (
                          language === 'ar' ? 'تحديث تلقائي كل ثانيتين' : language === 'fr' ? 'Mise à jour 2s' : 'Auto-updates 2s'
                        ) : (
                          language === 'ar' ? 'توقعات الذكاء الاصطناعي' : language === 'fr' ? 'Prédiction IA' : 'AI Forecast'
                        )}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="h-[280px] mt-2">
                    {isLoadingForecast ? (
                      <div className="w-full h-full flex flex-col items-center justify-center gap-2">
                        <Loader2 className="w-7 h-7 text-blue-500 animate-spin" />
                        <p className="text-xs text-slate-400">Computing energy forecast via AI models...</p>
                      </div>
                    ) : dashboardTimeframe === 'live' ? (
                      history.length < 2 ? (
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
                            {can(user, Feature.PRO_FORECAST_CURVE) && (
                              <Line
                                type="monotone"
                                dataKey="predicted"
                                stroke="#06B6D4"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                                activeDot={{ r: 5, fill: '#06B6D4', stroke: '#111827', strokeWidth: 2 }}
                              />
                            )}
                          </LineChart>
                        </ResponsiveContainer>
                      )
                    ) : (
                      forecastChartData && (
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={forecastChartData}>
                            <defs>
                              <linearGradient id="dashGradHist" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.2} />
                                <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                              </linearGradient>
                              <linearGradient id="dashGradPred" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#10B981" stopOpacity={0.15} />
                                <stop offset="100%" stopColor="#10B981" stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(59,130,246,0.06)" vertical={false} />
                            <XAxis
                              dataKey="time"
                              axisLine={false}
                              tickLine={false}
                              tick={{ fill: '#64748B', fontSize: 10 }}
                              interval={getDashboardTickInterval(forecastChartData.length, dashboardTimeframe)}
                            />
                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} domain={[0, 'auto']} />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: '#111827',
                                border: '1px solid rgba(59,130,246,0.15)',
                                borderRadius: '12px',
                                color: '#E2E8F0',
                                fontSize: '11px',
                              }}
                            />
                            <Area
                              type="monotone"
                              dataKey="historical"
                              stroke="#3B82F6"
                              strokeWidth={2}
                              fill="url(#dashGradHist)"
                              name={['24'].includes(dashboardTimeframe) ? "Historical (kW)" : "Historical (kWh)"}
                              connectNulls={false}
                            />
                            <Area
                              type="monotone"
                              dataKey="predicted"
                              stroke="#10B981"
                              strokeWidth={2}
                              strokeDasharray="5 3"
                              fill="url(#dashGradPred)"
                              name={['24'].includes(dashboardTimeframe) ? "Predicted (kW)" : "Predicted (kWh)"}
                              connectNulls={false}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      )
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Financial Estimates */}
              <Card className="glass-card border-white/[0.06]">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold text-white flex items-center justify-between">
                    <span>{language === 'ar' ? 'تقدير التكاليف الفورية' : language === 'fr' ? 'Estimation Financière' : 'Live Cost Estimation'}</span>
                    <Badge variant="outline" className={tariff.label.includes("Progressive") || tariff.label.includes("تدريجي") ? "border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[9px]" : "border-amber-500/20 text-amber-400 bg-amber-500/10 text-[9px]"}>
                      {tariff.label}
                    </Badge>
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400">
                    Moroccan ONEE National Tarif: {tariff.rate.toFixed(4)} MAD/kWh
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

                  {/* Divider */}
                  <div className="border-t border-white/[0.04] my-2" />

                  {/* Monthly Budget Tracker */}
                  <div className="p-3.5 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] text-slate-500 font-bold uppercase">
                        {language === 'ar' ? 'الميزانية الشهرية' : language === 'fr' ? 'Budget Mensuel' : 'Monthly Budget'}
                      </p>
                      <button
                        onClick={() => setIsEditingBudget(!isEditingBudget)}
                        className="text-[10px] text-blue-400 hover:text-blue-300 font-semibold transition-colors animate-pulse"
                      >
                        {budget ? (language === 'ar' ? 'تعديل' : language === 'fr' ? 'Modifier' : 'Edit') : (language === 'ar' ? 'تحديد' : language === 'fr' ? 'Définir' : 'Set Budget')}
                      </button>
                    </div>

                    {isEditingBudget ? (
                      <div className="flex flex-col gap-2 mt-1">
                        <div className="relative flex-1">
                          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-bold">
                            {systemSettings?.currency || 'MAD'}
                          </span>
                          <input
                            type="number"
                            value={budgetValue}
                            onChange={(e) => setBudgetValue(e.target.value)}
                            placeholder="Enter budget..."
                            className="w-full bg-[#111827] border border-white/10 rounded-lg py-1.5 pl-11 pr-2.5 text-xs text-white focus:outline-none focus:border-blue-500/50"
                            min="1"
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={handleSaveBudget}
                            disabled={isSavingBudget}
                            className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-[10px] h-8 px-3 font-bold"
                          >
                            {isSavingBudget ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              language === 'ar' ? 'حفظ' : language === 'fr' ? 'Enregistrer' : 'Save'
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setIsEditingBudget(false);
                              if (budget) setBudgetValue(budget.monthly_budget_mad.toString());
                            }}
                            className="text-slate-400 hover:text-white text-[10px] h-8 px-2 border border-white/10"
                          >
                            {language === 'ar' ? 'إلغاء' : language === 'fr' ? 'Annuler' : 'Cancel'}
                          </Button>
                        </div>
                      </div>
                    ) : budget ? (
                      <div className="space-y-2">
                        <div className="flex items-baseline justify-between mt-1">
                          <p className="text-sm text-slate-300">
                            <span className="text-xl font-bold text-white font-mono">
                              {projectedMonthlyCost.toFixed(0)}
                            </span>
                            <span className="text-slate-500 text-xs font-mono"> / {budget.monthly_budget_mad} {systemSettings?.currency || 'MAD'}</span>
                          </p>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            (projectedMonthlyCost / budget.monthly_budget_mad) > 0.9
                              ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                              : (projectedMonthlyCost / budget.monthly_budget_mad) > 0.7
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          }`}>
                            {((projectedMonthlyCost / budget.monthly_budget_mad) * 100).toFixed(0)}%
                          </span>
                        </div>
                        
                        {/* Progress Bar */}
                        <div className="w-full bg-[#111827] h-2 rounded-full overflow-hidden border border-white/[0.04]">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              (projectedMonthlyCost / budget.monthly_budget_mad) > 0.9
                                ? 'bg-red-500'
                                : (projectedMonthlyCost / budget.monthly_budget_mad) > 0.7
                                ? 'bg-amber-500'
                                : 'bg-emerald-500'
                            }`}
                            style={{ width: `${Math.min(100, (projectedMonthlyCost / budget.monthly_budget_mad) * 100)}%` }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-2 text-center">
                        <p className="text-xs text-slate-400 mb-2">No budget set for this month</p>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setIsEditingBudget(true)}
                          className="border-white/10 hover:bg-white/5 text-slate-300 text-[10px] h-7 px-3 rounded-lg w-full font-bold"
                        >
                          Set Budget Limit
                        </Button>
                      </div>
                    )}
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
                <CardContent className="space-y-4 relative min-h-[200px] flex flex-col justify-center">
                  {!can(user, Feature.PRO_FORECAST_CURVE) ? (
                    <div className="absolute inset-0 bg-[#0A0F1C]/90 backdrop-blur-[4px] z-10 flex flex-col items-center justify-center p-4 text-center rounded-b-xl">
                      <Lock className="w-5 h-5 text-blue-400 mb-2" />
                      <p className="text-xs font-bold text-white mb-1">Unlock Real-time Appliance Sub-metering</p>
                      <p className="text-[10px] text-slate-400 max-w-xs mb-3">
                        Track breakdown metrics for Kitchen, Laundry, and HVAC systems in real-time.
                      </p>
                      <Button
                        onClick={() => router.push('/plans')}
                        size="sm"
                        className="bg-blue-600 hover:bg-blue-500 text-white text-[10px] h-7 px-4 shadow-md shadow-blue-500/20"
                      >
                        Upgrade to Pro
                      </Button>
                    </div>
                  ) : null}
                  {/* kitchen sub1 */}
                  <div className={!can(user, Feature.PRO_FORECAST_CURVE) ? 'opacity-10 filter blur-[1px] select-none pointer-events-none' : ''}>
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
                  <div className={!can(user, Feature.PRO_FORECAST_CURVE) ? 'opacity-10 filter blur-[1px] select-none pointer-events-none' : ''}>
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
                  <div className={!can(user, Feature.PRO_FORECAST_CURVE) ? 'opacity-10 filter blur-[1px] select-none pointer-events-none' : ''}>
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

      </div>
    </AppLayout>
  );
}
