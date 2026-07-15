'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Server, Activity, CalendarClock, Target, Cpu } from 'lucide-react';
import { fetchWithAuth } from '@/services/api-client';

export default function ModelsPage() {
  const [models, setModels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadModels = async () => {
      try {
        const data = await fetchWithAuth('/api/v1/models/');
        setModels(data);
      } catch (err) {
        setError('Failed to load models. Please try again later.');
      } finally {
        setIsLoading(false);
      }
    };
    loadModels();
  }, []);

  return (
    <AppLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Model Registry</h1>
          <p className="text-slate-400">View and manage deployed ML forecasting models.</p>
        </div>

        <Card className="bg-[#111827] border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Server className="w-5 h-5 text-blue-400" />
              Deployed Models
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                <p className="text-sm text-slate-400">Fetching registry data...</p>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
                  <Activity className="w-6 h-6 text-red-500" />
                </div>
                <p className="text-sm text-red-400">{error}</p>
              </div>
            ) : models.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <Cpu className="w-12 h-12 text-slate-600" />
                <p className="text-sm text-slate-400">No deployed models found in the registry.</p>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-white/10">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-400 uppercase bg-black/20 border-b border-white/10">
                    <tr>
                      <th className="px-6 py-4 font-semibold">Model</th>
                      <th className="px-6 py-4 font-semibold">Horizon</th>
                      <th className="px-6 py-4 font-semibold">Version</th>
                      <th className="px-6 py-4 font-semibold">MAE</th>
                      <th className="px-6 py-4 font-semibold">RMSE</th>
                      <th className="px-6 py-4 font-semibold">Trained</th>
                      <th className="px-6 py-4 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {models.map((m) => (
                      <tr key={m.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-6 py-4 font-medium text-white flex items-center gap-2">
                          <Cpu className="w-4 h-4 text-slate-500" />
                          {m.display_name || m.name}
                        </td>
                        <td className="px-6 py-4 text-slate-300">
                          <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/20">
                            {m.version ? m.version.split('_')[0] : '24h'}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 font-mono text-xs text-slate-400">{m.version}</td>
                        <td className="px-6 py-4 text-slate-300">{m.mae?.toFixed(3) || '—'}</td>
                        <td className="px-6 py-4 text-slate-300">{m.rmse?.toFixed(3) || '—'}</td>
                        <td className="px-6 py-4 text-slate-400 flex items-center gap-1.5">
                          <CalendarClock className="w-3.5 h-3.5" />
                          {m.created_at ? new Date(m.created_at).toISOString().split('T')[0] : 'N/A'}
                        </td>
                        <td className="px-6 py-4">
                          <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-none uppercase text-[10px] tracking-wider">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
                            {m.status || 'Active'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
