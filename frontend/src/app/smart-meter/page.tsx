'use client';

import React, { useState, useEffect, useRef } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useI18n } from '@/lib/i18n';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, ShieldAlert, Cpu, Zap, Thermometer, Flame, PlayCircle, Loader2 } from 'lucide-react';

interface TelemetryFrame {
  timestamp: string;
  gap: number;      // active power (kW)
  grp: number;      // reactive power (kW)
  voltage: number;  // (V)
  intensity: number;// (A)
  sub_metering_1: number; // Kitchen (Wh)
  sub_metering_2: number; // Laundry (Wh)
  sub_metering_3: number; // HVAC (Wh)
}

export default function SmartMeterTelemetryPage() {
  const { t, language } = useI18n();
  const [liveData, setLiveData] = useState<TelemetryFrame | null>(null);
  const [history, setHistory] = useState<TelemetryFrame[]>([]);
  const [connected, setConnected] = useState(false);
  const [framesLog, setFramesLog] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Resolve websocket URL
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsProto = apiBase.startsWith('https') ? 'wss' : 'ws';
    const host = apiBase.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProto}://${host}/api/v1/forecast/smart-meter/live-ws`;

    console.log(`[TELEMETRY] Connecting to ${wsUrl}`);
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
          console.error('[TELEMETRY-WS] Error parsing frame:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('[TELEMETRY-WS] error:', err);
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
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [framesLog]);

  // Calculations for tariffs (EDF Peak: 6h-22h (€0.2460/kWh), Off-Peak: 22h-6h (€0.1828/kWh))
  const getTariffInfo = () => {
    const currentHour = new Date().getHours();
    const isOffPeak = currentHour >= 22 || currentHour < 6;
    const rate = isOffPeak ? 0.1828 : 0.2460;
    const label = isOffPeak 
      ? (language === 'ar' ? 'ساعات خارج الذروة Creuses' : language === 'fr' ? 'Heures Creuses' : 'Off-Peak Hours')
      : (language === 'ar' ? 'ساعات الذروة Pleines' : language === 'fr' ? 'Heures Pleines' : 'Peak Hours');
    return { rate, label, isOffPeak };
  };

  const tariff = getTariffInfo();
  const activePower = liveData?.gap || 0;
  
  // Cost per hour = active power (kW) * rate (€/kWh)
  const costPerHour = activePower * tariff.rate;
  const projectedDailyCost = costPerHour * 24;
  const projectedMonthlyCost = projectedDailyCost * 30.5;

  // Power Factor cos phi = GAP / sqrt(GAP^2 + GRP^2)
  const calculatePowerFactor = () => {
    if (!liveData) return 0.95;
    const { gap, grp } = liveData;
    if (gap === 0) return 1.0;
    const s = Math.sqrt(gap * gap + grp * grp);
    return Math.min(1.0, gap / s);
  };

  const powerFactor = calculatePowerFactor();

  // Chart data formatted for simple time view
  const chartData = history.map((h) => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    consumption: h.gap,
    voltage: h.voltage,
    intensity: h.intensity
  }));

  // Smart advice messages
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

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              <Zap className="w-6 h-6 text-emerald-400" />
              {language === 'ar' ? 'القياس المباشر للعداد الذكي' : language === 'fr' ? 'Télémesures Compteur Intelligent' : 'Smart Meter Live Telemetry'}
            </h1>
            <p className="text-slate-400 mt-1">
              {language === 'ar' ? 'مراقبة فورية وتحليل استهلاك الطاقة المباشر' : language === 'fr' ? 'Flux en temps réel de votre compteur Linky (API simulée).' : 'Real-time telemetry stream from your Enedis Linky utility meter.'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge className={connected ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/20" : "bg-red-500/15 text-red-400 border-red-500/20"}>
              <span className={`w-2 h-2 rounded-full mr-2 ${connected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
              {connected ? 'LIVE CONNECTION ACTIVE' : 'DISCONNECTED'}
            </Badge>
          </div>
        </div>

        {/* Smart AI Alert Panel */}
        <Card className={`border-l-4 ${
          advice.type === 'critical' ? 'border-red-500 bg-red-950/20' : 
          advice.type === 'warning' ? 'border-amber-500 bg-amber-950/20' : 
          'border-emerald-500 bg-emerald-950/20'
        } border-white/[0.06]`}>
          <CardContent className="p-4 flex items-start gap-3">
            <ShieldAlert className={`w-5 h-5 shrink-0 ${
              advice.type === 'critical' ? 'text-red-400' : 
              advice.type === 'warning' ? 'text-amber-400' : 
              'text-emerald-400'
            }`} />
            <div>
              <p className="text-xs font-semibold text-white uppercase tracking-wider">
                {language === 'ar' ? 'توصيات الذكاء الاصطناعي والأتمتة' : language === 'fr' ? 'Recommandations IA & Automatisation' : 'AI Automation Insights'}
              </p>
              <p className="text-sm text-slate-300 mt-1">
                {advice.text}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Metric Gauges Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Active Power Gauge */}
          <Card className="glass-card border-white/[0.06] overflow-hidden relative">
            <CardContent className="p-5 flex flex-col items-center justify-center text-center">
              <div className="relative w-28 h-28 flex items-center justify-center rounded-full border-4 border-dashed border-white/5">
                {/* Glowing ring */}
                <div className={`absolute inset-0 rounded-full border-4 ${
                  activePower > 4.0 ? 'border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.2)]' :
                  activePower > 2.2 ? 'border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.2)]' :
                  'border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                } transition-all duration-500`} />
                <div className="z-10">
                  <p className="text-2xl font-black text-white">{activePower ? activePower.toFixed(3) : '0.000'}</p>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">kW</p>
                </div>
              </div>
              <p className="text-xs font-semibold text-white mt-4 uppercase">
                {language === 'ar' ? 'الحمل النشط الفوري' : language === 'fr' ? 'Puissance Active' : 'Current Active Power'}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">Global Active Power</p>
            </CardContent>
          </Card>

          {/* Voltage Card */}
          <Card className="glass-card border-white/[0.06] flex items-center justify-between p-5">
            <div className="space-y-2">
              <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                {language === 'ar' ? 'الجهد الكهربائي' : language === 'fr' ? 'Tension' : 'Voltage'}
              </p>
              <p className="text-2xl font-bold text-white">
                {liveData ? `${liveData.voltage} V` : '—'}
              </p>
              <Badge variant="outline" className="border-blue-500/20 text-blue-400 bg-blue-500/10 text-[9px]">
                Safe range: 220V - 240V
              </Badge>
            </div>
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-blue-400" />
            </div>
          </Card>

          {/* Amperage Card */}
          <Card className="glass-card border-white/[0.06] flex items-center justify-between p-5">
            <div className="space-y-2">
              <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                {language === 'ar' ? 'التيار الإجمالي' : language === 'fr' ? 'Intensité' : 'Current draw'}
              </p>
              <p className="text-2xl font-bold text-white">
                {liveData ? `${liveData.intensity} A` : '—'}
              </p>
              <p className="text-[10px] text-slate-400">Current Intensity</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <Activity className="w-5 h-5 text-purple-400" />
            </div>
          </Card>

          {/* Power Factor Card */}
          <Card className="glass-card border-white/[0.06] flex items-center justify-between p-5">
            <div className="space-y-2">
              <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                {language === 'ar' ? 'معامل القدرة' : language === 'fr' ? 'Facteur de Puissance' : 'Power Factor'}
              </p>
              <p className="text-2xl font-bold text-white">
                {powerFactor.toFixed(3)}
              </p>
              <Badge variant="outline" className="border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[9px]">
                cos φ (optimal &gt; 0.90)
              </Badge>
            </div>
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center">
              <Zap className="w-5 h-5 text-cyan-400" />
            </div>
          </Card>
        </div>

        {/* Real-time Scrolling Recharts Chart */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Live scrolling curve */}
          <Card className="glass-card border-white/[0.06] lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold text-white flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
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
                    <Loader2 className="w-8 h-8 text-slate-600 animate-spin" />
                    <p className="text-xs text-slate-400">Collecting live telemetry stream frames...</p>
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
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Real-time Estimated costs & Tariff */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-white flex items-center justify-between">
                <span>{language === 'ar' ? 'تقدير التكاليف الفورية' : language === 'fr' ? 'Estimation Financière' : 'Live Cost Estimation'}</span>
                <Badge variant="outline" className={tariff.isOffPeak ? "border-emerald-500/20 text-emerald-400 bg-emerald-500/10 text-[9px]" : "border-amber-500/20 text-amber-400 bg-amber-500/10 text-[9px]"}>
                  {tariff.label}
                </Badge>
              </CardTitle>
              <CardDescription className="text-xs text-slate-400">
                Rate: €{tariff.rate}/kWh (EDF EDF Tarif Bleu)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Cost/Hour */}
              <div className="p-3 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80">
                <p className="text-[10px] text-slate-500 font-bold uppercase">{language === 'ar' ? 'التكلفة في الساعة' : language === 'fr' ? 'Coût Horaire' : 'Cost Per Hour'}</p>
                <p className="text-xl font-bold text-white mt-1">€ {costPerHour.toFixed(4)}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">Based on active power: {activePower.toFixed(2)} kW</p>
              </div>

              {/* Projected Day */}
              <div className="p-3 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80">
                <p className="text-[10px] text-slate-500 font-bold uppercase">{language === 'ar' ? 'التكلفة اليومية المتوقعة' : language === 'fr' ? 'Projection Journalière' : 'Projected Daily Cost'}</p>
                <p className="text-xl font-bold text-emerald-400 mt-1">€ {projectedDailyCost.toFixed(2)}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">If current usage holds for 24h</p>
              </div>

              {/* Projected Month */}
              <div className="p-3 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80">
                <p className="text-[10px] text-slate-500 font-bold uppercase">{language === 'ar' ? 'التكلفة الشهرية المتوقعة' : language === 'fr' ? 'Projection Mensuelle' : 'Projected Monthly Cost'}</p>
                <p className="text-xl font-black text-cyan-400 mt-1">€ {projectedMonthlyCost.toFixed(2)}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">Projected monthly billing cycle</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sub-meterings fluctuate loads & Telmetry raw frame logs */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Appliance Load breakdown */}
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

          {/* Raw frame logger */}
          <Card className="glass-card border-white/[0.06] flex flex-col h-[230px]">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <PlayCircle className="w-3.5 h-3.5 text-emerald-400" />
                Raw Linky Telemetry Log
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden p-3 pt-0">
              <div className="w-full h-full rounded-xl bg-black/60 border border-white/5 p-3 font-mono text-[9px] text-slate-400 overflow-y-auto space-y-1">
                {framesLog.map((log, i) => (
                  <p key={i} className={log.includes('[SYSTEM]') ? 'text-emerald-400' : 'text-slate-400'}>
                    {log}
                  </p>
                ))}
                <div ref={logEndRef} />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
