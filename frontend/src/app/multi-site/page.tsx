'use client';

import { useEffect, useMemo, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Activity, Building2, Clock3, RefreshCw, Zap } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { multiSiteApi } from '@/lib/api';
import type { Site } from '@/types';

export default function MultiSitePage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSites = async () => {
    setLoading(true); setError(null);
    try {
      const response = await multiSiteApi.getSites();
      setSites(response.data);
      setSelectedId((current) => current || response.data[0]?.id || '');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load sites.');
    } finally { setLoading(false); }
  };
  useEffect(() => { loadSites(); }, []);
  const selected = sites.find((site) => site.id === selectedId) || sites[0];
  const comparison = useMemo(() => sites.map((site) => ({ name: site.name, load: site.load, daily: site.dailyConsumption })), [sites]);
  const lastSeen = selected?.lastSeenAt ? new Date(selected.lastSeenAt).toLocaleString() : 'No readings yet';

  return <AppLayout><div className="mx-auto max-w-7xl space-y-6">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Building2 className="h-6 w-6 text-blue-400" />Sites</h1><p className="mt-1 text-sm text-slate-400">Monitoring and comparison only. Device control remains outside this release.</p></div><Button variant="outline" onClick={loadSites} disabled={loading} className="border-white/10 text-slate-200"><RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</Button></header>
    {error && <Card className="border-red-500/30 bg-red-500/10"><CardContent className="p-4 text-sm text-red-200">{error}</CardContent></Card>}
    {!loading && sites.length === 0 && <Card className="border-white/10 bg-[#111827]"><CardContent className="p-8 text-center text-sm text-slate-400">No sites are available yet. Complete setup to create your first site.</CardContent></Card>}
    {selected && <><div className="flex flex-wrap gap-2">{sites.map((site) => <button key={site.id} onClick={() => setSelectedId(site.id)} className={`rounded-md border px-3 py-2 text-sm ${site.id === selected.id ? 'border-blue-500 bg-blue-500/10 text-white' : 'border-white/10 text-slate-400 hover:text-white'}`}>{site.name}</button>)}</div>
    <div className="grid gap-4 md:grid-cols-4"><Metric icon={Activity} label="Current load" value={`${selected.load.toFixed(3)} kW`} detail={selected.source ? `Source: ${selected.source}` : 'No active source'} /><Metric icon={Zap} label="Today energy" value={`${selected.dailyConsumption.toFixed(3)} kWh`} detail="Measured intervals only" /><Metric icon={Zap} label="Monthly cost" value={`${selected.currency || 'MAD'} ${selected.monthlyCost.toFixed(2)}`} detail={`Peak: ${selected.peakPower.toFixed(3)} kW`} /><Metric icon={Clock3} label="Last reading" value={selected.ageSeconds === null || selected.ageSeconds === undefined ? 'Unavailable' : `${selected.ageSeconds}s ago`} detail={lastSeen} /></div>
    <div className="grid gap-6 lg:grid-cols-3"><Card className="border-white/10 bg-[#111827]/80 lg:col-span-2"><CardHeader><CardTitle className="text-base text-white">Site comparison</CardTitle><CardDescription>Current load and today&apos;s measured energy for your sites.</CardDescription></CardHeader><CardContent><div className="h-72">{comparison.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={comparison}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" /><XAxis dataKey="name" stroke="#94a3b8" fontSize={11} /><YAxis stroke="#94a3b8" fontSize={11} /><Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(255,255,255,0.12)' }} /><Bar dataKey="load" fill="#60a5fa" name="Current kW" /><Bar dataKey="daily" fill="#34d399" name="Today kWh" /></BarChart></ResponsiveContainer> : null}</div></CardContent></Card><Card className="border-white/10 bg-[#111827]/80"><CardHeader><CardTitle className="text-base text-white">Selected site</CardTitle><CardDescription>Data quality is based on the latest meter reading.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="flex items-center justify-between"><span className="text-sm text-slate-400">Meter</span><span className="text-sm text-white">{selected.meterId || 'Not connected'}</span></div><div className="flex items-center justify-between"><span className="text-sm text-slate-400">Status</span><Badge variant="outline" className="border-white/15 text-slate-200">{selected.status}</Badge></div><div className="border-t border-white/10 pt-4 text-xs leading-5 text-slate-400">No battery dispatch, load shedding, or appliance controls are enabled without an authorised device integration.</div></CardContent></Card></div></>}
  </div></AppLayout>;
}

function Metric({ icon: Icon, label, value, detail }: { icon: typeof Activity; label: string; value: string; detail: string }) {
  return <Card className="border-white/10 bg-[#111827]/80"><CardContent className="p-4"><div className="flex items-center justify-between"><p className="text-xs font-medium uppercase text-slate-400">{label}</p><Icon className="h-4 w-4 text-blue-400" /></div><p className="mt-3 text-xl font-semibold text-white">{value}</p><p className="mt-1 truncate text-xs text-slate-500" title={detail}>{detail}</p></CardContent></Card>;
}
