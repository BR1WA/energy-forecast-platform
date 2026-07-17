'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Sparkles, Leaf, TrendingDown, Star } from 'lucide-react';
import { dashboardApi } from '@/lib/api';

interface Recommendation {
  id: string;
  title: string;
  savings: number;
  difficulty: 'Easy' | 'Medium' | 'Hard';
  impact: 'Low' | 'Medium' | 'High';
  reliability: 'Low' | 'Medium' | 'High';
  stars: number;
  reason: string;
}

export default function RecommendationsPage() {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [carbonSaved, setCarbonSaved] = useState(18.2);

  const fetchRecs = async () => {
    try {
      const data = await dashboardApi.getSummary();
      setRecs(data.recommendations as unknown as Recommendation[]);
      setCarbonSaved(data.kpis.carbon_saved);
    } catch (err) {
      console.error('Failed to fetch recommendations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecs();
    // Poll every 5s to keep recommendations in sync with the simulator
    const interval = setInterval(fetchRecs, 5000);
    return () => clearInterval(interval);
  }, []);

  const totalSavings = recs.reduce((acc, curr) => acc + curr.savings, 0);

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
            <Sparkles className="text-indigo-400 w-8 h-8" /> AI Recommendations
          </h1>
          <p className="text-slate-400">Personalized actions to optimize consumption, reduce bills, and lower carbon emissions.</p>
        </div>

        {/* Overview Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-emerald-500 to-teal-400" />
            <CardContent className="p-6 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs text-slate-400 uppercase tracking-widest font-bold">Potential Monthly Savings</p>
                <p className="text-4xl font-extrabold text-white mt-1 font-mono">
                  {loading ? '...' : `${totalSavings} MAD`}
                </p>
                <p className="text-xs text-slate-500 mt-1">Calculated from active efficiency rules</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                <TrendingDown className="w-6 h-6 text-emerald-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md relative overflow-hidden">
            <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-purple-500 to-indigo-400" />
            <CardContent className="p-6 flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-xs text-slate-400 uppercase tracking-widest font-bold">Carbon Reduction Offset</p>
                <p className="text-4xl font-extrabold text-white mt-1 font-mono">
                  {loading ? '...' : `${carbonSaved} kg`}
                </p>
                <p className="text-xs text-slate-500 mt-1">Equivalent CO₂ emissions avoided</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center">
                <Leaf className="w-6 h-6 text-purple-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Priority list */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-white tracking-wide">Priority Savings Actions</h2>
          
          {loading ? (
            <div className="space-y-4">
              <div className="h-28 bg-[#111827]/40 rounded-xl border border-white/5 animate-pulse" />
              <div className="h-28 bg-[#111827]/40 rounded-xl border border-white/5 animate-pulse" />
            </div>
          ) : recs.length === 0 ? (
            <div className="p-12 text-center rounded-2xl border border-dashed border-white/10 bg-[#111827]/40">
              <p className="text-slate-400 font-medium">All systems operating optimally. No savings recommendations available.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {recs.map((rec) => (
                <Card key={rec.id} className="bg-[#111827]/80 border-white/10 hover:border-indigo-500/30 transition-all duration-300">
                  <CardContent className="p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                    <div className="space-y-3 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-base font-bold text-white">{rec.title}</span>
                        <div className="flex gap-0.5 ml-2">
                          {Array.from({ length: 5 }).map((_, i) => (
                            <Star
                              key={i}
                              className={`w-3.5 h-3.5 ${
                                i < rec.stars ? 'text-amber-400 fill-amber-400' : 'text-slate-600'
                              }`}
                            />
                          ))}
                        </div>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">{rec.reason}</p>
                      
                      <div className="flex flex-wrap gap-2 text-[10px]">
                        <Badge variant="outline" className="border-indigo-500/20 text-indigo-400 bg-indigo-500/10 font-mono">
                          Difficulty: {rec.difficulty}
                        </Badge>
                        <Badge variant="outline" className="border-cyan-500/20 text-cyan-400 bg-cyan-500/10 font-mono">
                          Impact: {rec.impact}
                        </Badge>
                        <Badge variant="outline" className="border-emerald-500/20 text-emerald-400 bg-emerald-500/10 font-mono">
                          Reliability: {rec.reliability}
                        </Badge>
                      </div>
                    </div>

                    <div className="flex flex-row md:flex-col items-baseline md:items-end justify-between w-full md:w-auto shrink-0 border-t md:border-t-0 border-white/5 pt-4 md:pt-0 gap-4">
                      <div className="text-left md:text-right">
                        <span className="text-[10px] text-slate-500 font-bold uppercase block">Monthly Savings</span>
                        <span className="text-xl font-extrabold text-emerald-400 font-mono">{rec.savings} MAD</span>
                      </div>
                      <Button size="sm" className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs h-8 px-4 rounded-lg">
                        Dismiss Action
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
