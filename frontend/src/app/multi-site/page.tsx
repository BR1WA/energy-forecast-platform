'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { toast } from 'sonner';
import {
  Building2,
  Lock,
  Activity,
  Zap,
  Cpu,
  Flame,
  Thermometer,
  Grid,
  CheckCircle2,
  AlertTriangle,
  Download,
  Power,
  TrendingUp,
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

const sitesData = [
  {
    id: 'site-casablanca',
    name: 'Casablanca Headquarters',
    meterId: 'CM-HQ-01',
    status: 'Active',
    load: 184.5,
    dailyConsumption: 2420,
    peakPower: 210,
    monthlyCost: 64800,
    circuits: [
      { name: 'Server Room A', status: 'Active', current: 120, power: 26.4, cosPhi: 0.98 },
      { name: 'HVAC Main', status: 'Active', current: 280, power: 61.6, cosPhi: 0.88 },
      { name: 'Production Line B', status: 'Active', current: 310, power: 68.2, cosPhi: 0.90 },
      { name: 'Office Lighting', status: 'Active', current: 130, power: 28.3, cosPhi: 0.95 },
    ]
  },
  {
    id: 'site-tangier',
    name: 'Tangier Logistics Hub',
    meterId: 'CM-TL-02',
    status: 'Active',
    load: 120.2,
    dailyConsumption: 1650,
    peakPower: 145,
    monthlyCost: 44200,
    circuits: [
      { name: 'EV Charging Stations', status: 'Active', current: 180, power: 39.6, cosPhi: 0.99 },
      { name: 'Conveyor Belts', status: 'Active', current: 220, power: 48.4, cosPhi: 0.85 },
      { name: 'Warehouse Lights', status: 'Active', current: 100, power: 22.0, cosPhi: 0.92 },
      { name: 'Office Pods', status: 'Active', current: 46, power: 10.2, cosPhi: 0.96 },
    ]
  },
  {
    id: 'site-marrakech',
    name: 'Marrakech Showroom',
    meterId: 'CM-MS-03',
    status: 'Active',
    load: 65.8,
    dailyConsumption: 920,
    peakPower: 80,
    monthlyCost: 24800,
    circuits: [
      { name: 'Display Lighting', status: 'Active', current: 110, power: 24.2, cosPhi: 0.97 },
      { name: 'HVAC Aircon', status: 'Active', current: 150, power: 33.0, cosPhi: 0.89 },
      { name: 'IT Infrastructure', status: 'Active', current: 30, power: 6.6, cosPhi: 0.95 },
      { name: 'Security & Access', status: 'Active', current: 9, power: 2.0, cosPhi: 0.90 },
    ]
  },
  {
    id: 'site-agadir',
    name: 'Agadir Production Plant',
    meterId: 'CM-AP-04',
    status: 'Maintenance',
    load: 0.0,
    dailyConsumption: 0,
    peakPower: 0,
    monthlyCost: 0,
    circuits: [
      { name: 'Assembly Line 1', status: 'Idle', current: 0, power: 0.0, cosPhi: 0.0 },
      { name: 'Main Compressor', status: 'Idle', current: 0, power: 0.0, cosPhi: 0.0 },
      { name: 'Plant Cooling', status: 'Idle', current: 0, power: 0.0, cosPhi: 0.0 },
      { name: 'Auxiliary System', status: 'Idle', current: 0, power: 0.0, cosPhi: 0.0 },
    ]
  }
];

export default function MultiSitePage() {
  const { user } = useAuth();
  const router = useRouter();
  const [selectedSiteId, setSelectedSiteId] = useState('site-casablanca');
  const [isBatteryBackupActive, setIsBatteryBackupActive] = useState(false);
  const [demandResponseStatus, setDemandResponseStatus] = useState<'connected' | 'shedding'>('connected');
  const [systemSettings, setSystemSettings] = useState<any>(null);

  const isEnterprise = user?.subscription_tier === 'enterprise';

  useEffect(() => {
    // Fetch system settings for localization and currency
    fetch('http://localhost:8000/api/v1/settings')
      .then((res) => res.json())
      .then((data) => setSystemSettings(data))
      .catch(console.error);
  }, []);

  const selectedSite = sitesData.find(s => s.id === selectedSiteId) || sitesData[0];

  const handleShedLoad = () => {
    if (demandResponseStatus === 'connected') {
      setDemandResponseStatus('shedding');
      toast.success('Demand Response Active: Shedding 35 kW of non-essential loads.');
    } else {
      setDemandResponseStatus('connected');
      toast.info('Demand Response Deactivated: Restoring normal site operation.');
    }
  };

  const handleToggleBattery = () => {
    setIsBatteryBackupActive(!isBatteryBackupActive);
    if (!isBatteryBackupActive) {
      toast.success('Emergency Battery Bank Engaged: Peak-shaving in progress.');
    } else {
      toast.info('Battery Bank Disengaged: Grid power re-established.');
    }
  };

  const handleDownloadAudit = () => {
    toast.success(`Multi-site audit logs exported successfully for ${selectedSite.name}.`);
  };

  // 24 Hour load simulation for selected site
  const hourlyLoadData = Array.from({ length: 24 }, (_, i) => {
    const isPeakHour = i >= 8 && i <= 18;
    const baseLoad = selectedSite.load * (isPeakHour ? 1.15 : 0.75);
    const randomFactor = 0.95 + Math.sin((i / 24) * Math.PI) * 0.1;
    let actualLoad = baseLoad * randomFactor;
    
    if (isBatteryBackupActive && i >= 12 && i <= 15) {
      // Shave peak loads if battery is active
      actualLoad -= 25;
    }
    if (demandResponseStatus === 'shedding' && isPeakHour) {
      actualLoad -= 35;
    }

    return {
      hour: `${String(i).padStart(2, '0')}:00`,
      actual: Math.max(0, Math.round(actualLoad)),
      forecast: Math.round(baseLoad),
    };
  });

  // Compare active power across all active sites
  const siteComparisonData = sitesData.map(s => ({
    name: s.name.split(' ')[0], // just City name
    load: s.load,
    daily: s.dailyConsumption,
  }));

  if (!isEnterprise) {
    return (
      <AppLayout>
        <div className="min-h-[75vh] flex items-center justify-center">
          <Card className="glass-card border-white/[0.06] relative overflow-hidden max-w-2xl w-full p-8 text-center">
            <div className="absolute inset-0 bg-[#0A0F1C]/90 backdrop-blur-[6px] z-10 flex flex-col items-center justify-center p-6 text-center">
              <div className="w-14 h-14 rounded-full bg-blue-500/10 flex items-center justify-center mb-5">
                <Lock className="w-7 h-7 text-blue-400" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Multi-Site Grid Manager</h2>
              <Badge className="bg-gradient-to-r from-purple-500 to-indigo-500 text-white border-0 text-[10px] mb-4 uppercase tracking-wider font-semibold">
                Enterprise Exclusive
              </Badge>
              <p className="text-sm text-slate-400 max-w-md mb-8">
                Aggregate electrical telemetry, manage demand response integrations, simulate load shedding, and compare power metrics across multiple geographic sites in real-time.
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  onClick={() => router.push('/plans')}
                  className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-8 shadow-lg shadow-blue-500/20"
                >
                  Upgrade to Enterprise Plan
                </Button>
                <Button
                  onClick={() => router.push('/dashboard')}
                  variant="outline"
                  className="border-white/10 hover:bg-white/5 text-slate-300"
                >
                  Return to Dashboard
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Building2 className="w-6 h-6 text-blue-400" />
              Multi-Site Grid Manager
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Real-time multi-site telemetry, load aggregation, and intelligent grid integration
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <select
              value={selectedSiteId}
              onChange={(e) => setSelectedSiteId(e.target.value)}
              className="bg-[#0D1527] border border-white/[0.08] text-slate-200 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5 outline-none hover:bg-[#121B32] transition-colors"
            >
              {sitesData.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.status})
                </option>
              ))}
            </select>

            <Button
              onClick={handleDownloadAudit}
              variant="outline"
              className="border-white/10 hover:bg-white/5 text-slate-300 flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Export Site Logs
            </Button>
          </div>
        </div>

        {/* Telemetry Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            {
              label: 'Grid Status',
              value: selectedSite.status,
              trend: selectedSite.meterId,
              icon: Grid,
              positive: selectedSite.status === 'Active',
            },
            {
              label: 'Active Grid Load',
              value: `${selectedSite.load.toFixed(1)} kW`,
              trend: 'Real-time telemetry',
              icon: Activity,
              positive: selectedSite.load < selectedSite.peakPower * 0.9,
            },
            {
              label: 'Aggregate Daily Usage',
              value: `${selectedSite.dailyConsumption.toLocaleString()} kWh`,
              trend: `Peak Power: ${selectedSite.peakPower} kW`,
              icon: Zap,
              positive: true,
            },
            {
              label: 'Estimated Cost (Monthly)',
              value: `${systemSettings?.currency || 'MAD'} ${selectedSite.monthlyCost.toLocaleString()}`,
              trend: 'Based on localized tariff',
              icon: TrendingUp,
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
                    <div className="flex items-center gap-2 mt-1">
                      {stat.label === 'Grid Status' && (
                        <div className={`w-2.5 h-2.5 rounded-full ${stat.positive ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500 animate-pulse'}`} />
                      )}
                      <p className="text-lg font-bold text-white">
                        {stat.value}
                      </p>
                    </div>
                    <p className="text-xs mt-0.5 text-slate-400">
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

        {/* Charts & Graphs */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Facility Load Profile */}
          <Card className="glass-card border-white/[0.06] lg:col-span-2">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base font-semibold text-white">Facility Demand Profile (24h)</CardTitle>
                <CardDescription className="text-xs text-slate-400">Predicted vs active loads for {selectedSite.name}</CardDescription>
              </div>
              <div className="flex items-center gap-2">
                {isBatteryBackupActive && (
                  <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] animate-pulse">
                    Peak-Shaving Active
                  </Badge>
                )}
                {demandResponseStatus === 'shedding' && (
                  <Badge className="bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[10px] animate-pulse">
                    DR Load Shed
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={hourlyLoadData}>
                    <defs>
                      <linearGradient id="multiSiteActual" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(59,130,246,0.06)" vertical={false} />
                    <XAxis dataKey="hour" axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} interval={3} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} />
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
                    <Area type="monotone" dataKey="actual" stroke="#3B82F6" strokeWidth={2.5} fill="url(#multiSiteActual)" name="Active Load (kW)" />
                    <Area type="monotone" dataKey="forecast" stroke="#94A3B8" strokeWidth={1.5} strokeDasharray="4 4" fill="none" name="Baseline Forecast (kW)" opacity={0.6} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Cross-Facility Comparison */}
          <Card className="glass-card border-white/[0.06]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-white">Grid Load Comparison</CardTitle>
              <CardDescription className="text-xs text-slate-400">Comparing active load across sites</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={siteComparisonData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(59,130,246,0.06)" vertical={false} />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748B', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#111827',
                        border: '1px solid rgba(59,130,246,0.15)',
                        borderRadius: '12px',
                        color: '#E2E8F0',
                      }}
                    />
                    <Bar dataKey="load" fill="#8B5CF6" radius={[4, 4, 0, 0]} name="Active Load (kW)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sub-metered Circuits & Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Circuits telemetry */}
          <Card className="glass-card border-white/[0.06] lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-white">Sub-metered Circuits Telemetry</CardTitle>
              <CardDescription className="text-xs text-slate-400">Individual electrical metrics for the current facility circuits</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                      <th className="p-4 text-slate-400 font-medium uppercase tracking-wider">Circuit Name</th>
                      <th className="p-4 text-slate-400 font-medium uppercase tracking-wider">Status</th>
                      <th className="p-4 text-slate-400 font-medium uppercase tracking-wider">Current Draw (A)</th>
                      <th className="p-4 text-slate-400 font-medium uppercase tracking-wider">Active Power (kW)</th>
                      <th className="p-4 text-slate-400 font-medium uppercase tracking-wider">Power Factor (cos φ)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedSite.circuits.map((circuit, idx) => (
                      <tr key={idx} className="border-b border-white/[0.04] hover:bg-white/[0.01] transition-colors">
                        <td className="p-4 font-semibold text-slate-200">{circuit.name}</td>
                        <td className="p-4">
                          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium ${circuit.status === 'Active' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${circuit.status === 'Active' ? 'bg-emerald-500' : 'bg-slate-500'}`} />
                            {circuit.status}
                          </span>
                        </td>
                        <td className="p-4 font-mono text-slate-300">{circuit.current} A</td>
                        <td className="p-4 font-mono text-slate-300">{circuit.power.toFixed(1)} kW</td>
                        <td className="p-4 font-mono text-slate-300">{circuit.cosPhi.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Grid control panels */}
          <div className="space-y-6">
            {/* Demand Response DR Integration */}
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                  <Grid className="w-5 h-5 text-blue-400" />
                  Grid Integrations
                </CardTitle>
                <CardDescription className="text-xs text-slate-400">Manage connections to ONEE national energy grid</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-3.5 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80 flex items-center justify-between">
                  <div>
                    <p className="text-[10px] text-slate-500 font-bold uppercase">DR Protocol</p>
                    <p className="text-sm font-semibold text-white mt-0.5">ONEE Demand Response</p>
                  </div>
                  <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-medium flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Online
                  </Badge>
                </div>

                <div className="flex gap-3">
                  <Button
                    onClick={handleShedLoad}
                    className={`flex-1 flex items-center justify-center gap-2 font-semibold text-xs py-2.5 rounded-lg border transition-all duration-300 ${
                      demandResponseStatus === 'shedding'
                        ? 'bg-amber-600 hover:bg-amber-500 text-white border-transparent shadow-lg shadow-amber-500/10'
                        : 'bg-transparent border-white/10 hover:bg-white/5 text-slate-300'
                    }`}
                  >
                    <AlertTriangle className="w-4 h-4" />
                    {demandResponseStatus === 'shedding' ? 'Cancel Load Shed' : 'Shed Non-Essential'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Smart Micro-grid Controls */}
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold text-white flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-purple-400" />
                  Peak-Shaving Systems
                </CardTitle>
                <CardDescription className="text-xs text-slate-400">Dispatch local facility batteries during peak tariffs</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-3.5 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/80 flex items-center justify-between">
                  <div>
                    <p className="text-[10px] text-slate-500 font-bold uppercase">Battery System</p>
                    <p className="text-sm font-semibold text-white mt-0.5">Facility Storage Bank</p>
                  </div>
                  <Badge className={`text-[10px] font-medium flex items-center gap-1 ${
                    isBatteryBackupActive
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                  }`}>
                    {isBatteryBackupActive ? 'Discharging' : 'Standby'}
                  </Badge>
                </div>

                <Button
                  onClick={handleToggleBattery}
                  className={`w-full flex items-center justify-center gap-2 font-semibold text-xs py-2.5 rounded-lg border transition-all duration-300 ${
                    isBatteryBackupActive
                      ? 'bg-purple-600 hover:bg-purple-500 text-white border-transparent shadow-lg shadow-purple-500/10'
                      : 'bg-transparent border-white/10 hover:bg-white/5 text-slate-300'
                  }`}
                >
                  <Power className="w-4 h-4" />
                  {isBatteryBackupActive ? 'Disengage Battery Bank' : 'Engage Battery Bank'}
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
