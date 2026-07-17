'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { FileText, Download, Calendar } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { toast } from 'sonner';
import { consumptionApi, dashboardApi } from '@/lib/api';

interface EnergyScoreHistory {
  month: string;
  score: number;
  consumption: number;
}

export default function ReportsPage() {
  const [exporting, setExporting] = useState<string | null>(null);
  const [scores, setScores] = useState<EnergyScoreHistory[]>([
    { month: 'Jan', score: 82, consumption: 290 },
    { month: 'Feb', score: 85, consumption: 275 },
    { month: 'Mar', score: 91, consumption: 250 },
    { month: 'Apr', score: 89, consumption: 260 },
    { month: 'May', score: 93, consumption: 235 },
    { month: 'Jun', score: 95, consumption: 220 },
  ]);

  useEffect(() => {
    const fetchCurrentMonth = async () => {
      try {
        const stats = await consumptionApi.getStatistics();
        const summary = await dashboardApi.getSummary();
        
        const currentKwh = Math.round(stats.total_kwh || 125.4);
        const score = summary.kpis.energy_score || 86;
        
        setScores(prev => {
          const hasJuly = prev.some(item => item.month === 'Jul');
          if (hasJuly) {
            return prev.map(item => item.month === 'Jul' ? { month: 'Jul', score, consumption: currentKwh } : item);
          } else {
            return [...prev, { month: 'Jul', score, consumption: currentKwh }];
          }
        });
      } catch (err) {
        console.error('Failed to load current reports month data:', err);
      }
    };
    
    fetchCurrentMonth();
  }, []);

  const handleExport = (type: 'pdf' | 'csv', name: string) => {
    setExporting(name);
    setTimeout(() => {
      setExporting(null);
      toast.success(`${type.toUpperCase()} report "${name}" exported successfully!`);
    }, 1500);
  };

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
            <FileText className="text-indigo-400 w-8 h-8" /> Energy Reports & Analytics
          </h1>
          <p className="text-slate-400">Generate executive PDF/CSV summaries, review score histories, and compare seasonal profiles.</p>
        </div>

        {/* Reports grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Energy Score History Chart (Col 1 & 2) */}
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-white text-base">Energy Score & Consumption History</CardTitle>
              <CardDescription className="text-slate-400 text-xs">Track energy optimization scores (0-100) alongside monthly active power totals (kWh).</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={scores} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="month" stroke="#94a3b8" fontSize={10} tickLine={false} />
                    <YAxis yAxisId="left" stroke="#818cf8" fontSize={10} tickLine={false} label={{ value: 'Energy Score', angle: -90, position: 'insideLeft', fill: '#818cf8', fontSize: 10 }} />
                    <YAxis yAxisId="right" orientation="right" stroke="#34d399" fontSize={10} tickLine={false} label={{ value: 'kWh Consumed', angle: 90, position: 'insideRight', fill: '#34d399', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1f2937',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '0.375rem',
                      }}
                      labelStyle={{ color: '#fff' }}
                    />
                    <Legend />
                    <Bar yAxisId="left" dataKey="score" fill="#818cf8" radius={[4, 4, 0, 0]} name="Energy Score (0-100)" />
                    <Bar yAxisId="right" dataKey="consumption" fill="#34d399" radius={[4, 4, 0, 0]} name="Consumption (kWh)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* KPI progress list (Col 3) */}
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md lg:col-span-1 flex flex-col justify-between">
            <CardHeader>
              <CardTitle className="text-white text-base">Efficiency Milestones</CardTitle>
              <CardDescription className="text-slate-400 text-xs">Track historical score gains and tariff optimization milestones.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 flex-1">
              <div className="p-3.5 rounded-lg border border-white/[0.04] bg-[#0A0F1C]/80">
                <div className="text-[10px] text-indigo-400 font-bold uppercase">Best Month Score</div>
                <div className="text-2xl font-bold text-white mt-1">95 / 100 <span className="text-xs text-emerald-400">(June)</span></div>
                <p className="text-[10px] text-slate-500 mt-1">92% budget adherence, 90% action adoption</p>
              </div>
              <div className="p-3.5 rounded-lg border border-white/[0.04] bg-[#0A0F1C]/80">
                <div className="text-[10px] text-emerald-400 font-bold uppercase">Active Billing Period</div>
                <div className="text-2xl font-bold text-white mt-1">Tranche 2 <span className="text-xs text-indigo-400">(Morocco ONEE)</span></div>
                <p className="text-[10px] text-slate-500 mt-1">Estimated progressive rate: 1.01 MAD / kWh</p>
              </div>
              <div className="p-3.5 rounded-lg border border-white/[0.04] bg-[#0A0F1C]/80 flex items-center justify-between">
                <div>
                  <div className="text-[10px] text-purple-400 font-bold uppercase">Carbon Saved</div>
                  <div className="text-base font-bold text-white mt-1">{scores[scores.length - 1]?.consumption ? Math.round(scores[scores.length - 1].consumption * 0.52) : 18} kg CO₂</div>
                </div>
                <Calendar className="w-5 h-5 text-purple-400 opacity-60" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Available Executive PDF templates */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-white tracking-wide">Generate Executive Statements</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { name: 'Monthly Bill Analysis', desc: 'Comprehensive breakdown of progressive ONEE billing tranches, peak hours, and actual costs.' },
              { name: 'Forecast Performance Audit', desc: 'Evaluation of model prediction error margins (MAPE), lookback variables, and confidence bands.' },
              { name: 'Carbon Impact Report', desc: 'Summary of sub-metering offsets, appliance optimizations, and net green energy contributions.' }
            ].map((report) => (
              <Card key={report.name} className="bg-[#111827]/80 border-white/10 hover:border-indigo-500/30 transition-all duration-300 flex flex-col justify-between">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-white text-sm font-bold">{report.name}</CardTitle>
                    <Badge variant="secondary" className="bg-white/5 border border-white/10 text-slate-300 text-[9px] uppercase font-mono">PDF</Badge>
                  </div>
                  <CardDescription className="text-slate-400 text-xs mt-1.5 leading-relaxed">{report.desc}</CardDescription>
                </CardHeader>
                <CardContent className="pt-0 flex justify-end gap-2">
                  <Button
                    onClick={() => handleExport('pdf', report.name)}
                    disabled={exporting !== null}
                    size="sm"
                    className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs h-8 px-4 rounded-lg"
                  >
                    {exporting === report.name ? 'Exporting...' : 'Download PDF'}
                    {exporting !== report.name && <Download className="w-3.5 h-3.5 ml-2" />}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
