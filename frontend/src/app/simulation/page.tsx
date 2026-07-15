'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Play, Square, RotateCcw, Activity, RefreshCw, Home, Users, Thermometer, Wind, Zap, Sun } from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { simulationApi, consumptionApi } from '@/lib/api';
import { toast } from 'sonner';

export default function SimulationPage() {
  const [statusLoading, setStatusLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [uptime, setUptime] = useState(0);
  const [history, setHistory] = useState<Array<{ kw: number; timestamp: string; timeLabel: string }>>([]);

  // Virtual House Slider States
  const [dayPart, setDayPart] = useState<'morning' | 'afternoon' | 'evening' | 'night'>('evening');
  const [occupants, setOccupants] = useState<number>(2);
  const [temperature, setTemperature] = useState<number>(25);
  const [acLevel, setAcLevel] = useState<'off' | 'low' | 'medium' | 'high'>('medium');
  const [washingMachine, setWashingMachine] = useState<boolean>(false);
  const [solar, setSolar] = useState<'off' | 'low' | 'high'>('off');

  const [configuring, setConfiguring] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await simulationApi.getStatus();
      setIsRunning(res.is_running);
      setUptime(res.uptime || 0);
      
      // Populate slider states from backend config if we aren't currently editing
      if (res.day_part) setDayPart(res.day_part as any);
      if (res.occupants !== undefined) setOccupants(res.occupants);
      if (res.temperature !== undefined) setTemperature(res.temperature);
      if (res.ac_level) setAcLevel(res.ac_level as any);
      if (res.washing_machine !== undefined) setWashingMachine(res.washing_machine);
      if (res.solar) setSolar(res.solar as any);
    } catch (err) {
      console.error('Failed to fetch simulation status', err);
    } finally {
      setStatusLoading(false);
    }
  };

  const fetchTelemetryHistory = async () => {
    try {
      const historyData = await consumptionApi.getHistory();
      const formatted = (historyData || []).reverse().map((item: any) => {
        const date = new Date(item.timestamp);
        const timeLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        return {
          ...item,
          timeLabel,
        };
      });
      setHistory(formatted.slice(-30));
    } catch (err) {
      console.error('Failed to fetch telemetry history for simulation view', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchTelemetryHistory();

    const interval = setInterval(() => {
      fetchStatus();
      fetchTelemetryHistory();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      await simulationApi.start();
      setIsRunning(true);
      toast.success('Virtual House simulator started!');
      fetchTelemetryHistory();
    } catch (err) {
      console.error('Failed to start simulation', err);
    }
  };

  const handleStop = async () => {
    try {
      await simulationApi.stop();
      setIsRunning(false);
      toast.info('Virtual House simulator paused.');
    } catch (err) {
      console.error('Failed to stop simulation', err);
    }
  };

  const handleReset = async () => {
    try {
      await simulationApi.reset();
      setIsRunning(false);
      setUptime(0);
      setHistory([]);
      toast.success('Simulation feed reset successfully.');
    } catch (err) {
      console.error('Failed to reset simulation', err);
    }
  };

  const handleApplyScenario = async () => {
    try {
      setConfiguring(true);
      await simulationApi.configure({
        day_part: dayPart,
        occupants,
        temperature,
        ac_level: acLevel,
        washing_machine: washingMachine,
        solar,
      });
      toast.success('Virtual House scenario applied!');
      fetchTelemetryHistory();
    } catch (err) {
      console.error('Failed to apply scenario settings', err);
      toast.error('Failed to apply simulation settings.');
    } finally {
      setConfiguring(false);
    }
  };

  function formatDuration(seconds: number): string {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
            <Home className="text-indigo-400 w-8 h-8" /> Virtual House Simulator
          </h1>
          <p className="text-slate-400">Model household behaviors, switch appliances, and watch energy curves shift in real time.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls Card */}
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md lg:col-span-1 flex flex-col justify-between">
            <CardHeader className="pb-3 border-b border-white/5">
              <CardTitle className="text-white text-base">Simulation Controller</CardTitle>
              <CardDescription className="text-xs text-slate-400">Run or pause the background Linky telemetry generation.</CardDescription>
            </CardHeader>
            <CardContent className="p-5 space-y-6 flex-1">
              <div className="flex flex-col items-center justify-center p-6 rounded-xl bg-black/20 border border-white/5 text-center">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">State</div>
                {statusLoading ? (
                  <div className="text-lg font-bold text-slate-400 animate-pulse">Checking status...</div>
                ) : isRunning ? (
                  <div className="space-y-1">
                    <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold animate-pulse">
                      ● RUNNING
                    </Badge>
                    <div className="text-2xl font-mono font-bold text-white mt-2">
                      {formatDuration(uptime)}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <Badge className="bg-slate-500/10 text-slate-400 border border-white/10 text-[10px] font-bold">
                      ● INACTIVE
                    </Badge>
                    <div className="text-2xl font-mono font-bold text-slate-500 mt-2">
                      00:00:00
                    </div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-3 gap-2">
                <Button
                  onClick={handleStart}
                  disabled={isRunning || statusLoading}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs h-9 rounded-lg"
                >
                  <Play className="h-4 w-4 mr-1.5" /> Start
                </Button>
                <Button
                  onClick={handleStop}
                  disabled={!isRunning || statusLoading}
                  className="bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs h-9 rounded-lg"
                >
                  <Square className="h-4 w-4 mr-1.5" /> Pause
                </Button>
                <Button
                  onClick={handleReset}
                  disabled={statusLoading}
                  variant="outline"
                  className="border-white/10 text-white hover:bg-white/5 font-bold text-xs h-9 rounded-lg"
                >
                  <RotateCcw className="h-4 w-4 mr-1.5" /> Reset
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Interactive virtual house config */}
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md lg:col-span-2">
            <CardHeader className="pb-3 border-b border-white/5">
              <CardTitle className="text-white text-base">Virtual House Configuration</CardTitle>
              <CardDescription className="text-xs text-slate-400">Configure parameters to trigger real-time anomalies and recommendations.</CardDescription>
            </CardHeader>
            <CardContent className="p-5 space-y-5">
              {/* Day Part */}
              <div className="space-y-2">
                <label className="text-xs text-slate-400 font-semibold flex items-center gap-1.5">
                  <Sun className="w-3.5 h-3.5 text-indigo-400" /> Day Part Selector
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {(['morning', 'afternoon', 'evening', 'night'] as const).map((part) => (
                    <button
                      key={part}
                      onClick={() => setDayPart(part)}
                      className={`text-xs py-2 rounded-lg font-bold border transition-colors ${
                        dayPart === part
                          ? 'bg-indigo-600 text-white border-indigo-500'
                          : 'bg-[#1f2937]/30 border-white/5 text-slate-400 hover:bg-white/5'
                      }`}
                    >
                      {part.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sliders row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Occupants */}
                <div className="space-y-2">
                  <label className="text-xs text-slate-400 font-semibold flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <Users className="w-3.5 h-3.5 text-indigo-400" /> People Home
                    </span>
                    <span className="text-white font-mono text-xs">{occupants}</span>
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={occupants}
                    onChange={(e) => setOccupants(Number(e.target.value))}
                    className="w-full accent-indigo-500 bg-white/5 rounded-lg appearance-none h-1.5"
                  />
                </div>

                {/* Temperature */}
                <div className="space-y-2">
                  <label className="text-xs text-slate-400 font-semibold flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <Thermometer className="w-3.5 h-3.5 text-indigo-400" /> Outside Temperature
                    </span>
                    <span className="text-white font-mono text-xs">{temperature}°C</span>
                  </label>
                  <input
                    type="range"
                    min="15"
                    max="40"
                    value={temperature}
                    onChange={(e) => setTemperature(Number(e.target.value))}
                    className="w-full accent-indigo-500 bg-white/5 rounded-lg appearance-none h-1.5"
                  />
                </div>
              </div>

              {/* Switches row */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* AC Level */}
                <div className="space-y-2">
                  <label className="text-xs text-slate-400 font-semibold flex items-center gap-1.5">
                    <Wind className="w-3.5 h-3.5 text-indigo-400" /> Air Conditioning
                  </label>
                  <select
                    value={acLevel}
                    onChange={(e: any) => setAcLevel(e.target.value)}
                    className="w-full bg-[#111827] border border-white/10 rounded-lg py-1.5 px-2.5 text-xs text-white focus:outline-none"
                  >
                    <option value="off">OFF</option>
                    <option value="low">LOW</option>
                    <option value="medium">MEDIUM</option>
                    <option value="high">HIGH</option>
                  </select>
                </div>

                {/* Washing Machine */}
                <div className="space-y-2">
                  <label className="text-xs text-slate-400 font-semibold flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-indigo-400" /> Washing Machine
                  </label>
                  <select
                    value={washingMachine ? 'on' : 'off'}
                    onChange={(e: any) => setWashingMachine(e.target.value === 'on')}
                    className="w-full bg-[#111827] border border-white/10 rounded-lg py-1.5 px-2.5 text-xs text-white focus:outline-none"
                  >
                    <option value="off">OFF</option>
                    <option value="on">ACTIVE</option>
                  </select>
                </div>

                {/* Solar generation */}
                <div className="space-y-2">
                  <label className="text-xs text-slate-400 font-semibold flex items-center gap-1.5">
                    <Sun className="w-3.5 h-3.5 text-indigo-400" /> Solar Panels
                  </label>
                  <select
                    value={solar}
                    onChange={(e: any) => setSolar(e.target.value)}
                    className="w-full bg-[#111827] border border-white/10 rounded-lg py-1.5 px-2.5 text-xs text-white focus:outline-none"
                  >
                    <option value="off">OFF</option>
                    <option value="low">LOW</option>
                    <option value="high">HIGH</option>
                  </select>
                </div>
              </div>

              <Button
                onClick={handleApplyScenario}
                disabled={configuring}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold h-9 rounded-lg"
              >
                {configuring ? <RefreshCw className="w-4 h-4 animate-spin" /> : 'Apply House Scenario'}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Real-time feed graph */}
        <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="text-white text-base">Active Simulated Feed (Realtime)</CardTitle>
              <CardDescription className="text-xs text-slate-400">Live active power logs committed by background thread.</CardDescription>
            </div>
            <Activity className="h-4 w-4 text-emerald-400" />
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <div className="h-72 flex flex-col items-center justify-center text-slate-400 text-center space-y-2">
                <Play className="h-8 w-8 text-slate-500" />
                <div>No live simulated readings yet. Click **Start** to begin generating load events.</div>
              </div>
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="timeLabel" stroke="#94a3b8" fontSize={10} tickLine={false} />
                    <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} unit=" kW" domain={['auto', 'auto']} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '0.375rem',
                      }}
                      labelStyle={{ color: '#fff' }}
                      itemStyle={{ color: '#10b981' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="kw"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={false}
                      name="Telemetry (kW)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
