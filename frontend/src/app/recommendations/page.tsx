'use client';

import { useCallback, useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, CircleAlert, Loader2, RotateCcw, Sparkles, X } from 'lucide-react';
import { toast } from 'sonner';
import { recommendationsApi } from '@/lib/api';
import type { Recommendation } from '@/types';

export default function RecommendationsPage() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<number | null>(null);
  const [showClosed, setShowClosed] = useState(false);

  const load = useCallback(async (includeClosed = false) => {
    setLoading(true);
    try {
      setItems(await recommendationsApi.getAll(includeClosed));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to load recommendations.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(false); }, [load]);

  const updateStatus = async (item: Recommendation, status: Recommendation['status']) => {
    setUpdating(item.id);
    try {
      const updated = await recommendationsApi.updateStatus(item.id, status);
      setItems((current) => showClosed
        ? current.map((entry) => entry.id === updated.id ? updated : entry)
        : current.filter((entry) => entry.id !== updated.id));
      toast.success(status === 'completed' ? 'Action marked complete.' : status === 'dismissed' ? 'Action dismissed.' : 'Action reopened.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update this action.');
    } finally {
      setUpdating(null);
    }
  };

  const toggleHistory = () => {
    const next = !showClosed;
    setShowClosed(next);
    load(next);
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Sparkles className="h-6 w-6 text-blue-400" />Recommendations</h1>
            <p className="mt-1 text-sm text-slate-400">Actions are generated from persisted alert evidence and your configured tariff, never appliance guesses.</p>
          </div>
          <Button variant="outline" onClick={toggleHistory} className="gap-2 border-white/10 text-white hover:bg-white/5">
            <RotateCcw className="h-4 w-4" />{showClosed ? 'Open actions only' : 'Show history'}
          </Button>
        </div>

        {loading ? <div className="flex min-h-48 items-center justify-center text-slate-400"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Loading actions...</div> : items.length ? (
          <div className="space-y-4">
            {items.map((item) => {
              const isOpen = item.status === 'open';
              const isUpdating = updating === item.id;
              const observed = typeof item.evidence_json.observed_kw === 'number' ? item.evidence_json.observed_kw.toFixed(2) : null;
              const threshold = typeof item.evidence_json.threshold_kw === 'number' ? item.evidence_json.threshold_kw.toFixed(2) : null;
              return <Card key={item.id} className="border-white/[0.08] bg-[#111827]/80">
                <CardHeader className="pb-3"><div className="flex items-start justify-between gap-4"><CardTitle className="flex items-center gap-2 text-base text-white">{item.category === 'peak_load' ? <CircleAlert className="h-5 w-5 text-amber-400" /> : <CircleAlert className="h-5 w-5 text-rose-400" />}{item.title}</CardTitle><span className="shrink-0 rounded border border-white/10 px-2 py-1 text-xs capitalize text-slate-300">{item.status}</span></div></CardHeader>
                <CardContent className="space-y-4"><p className="text-sm leading-6 text-slate-300">{item.message}</p>
                  {observed && threshold && <p className="rounded border border-white/[0.06] bg-black/10 p-3 text-sm text-slate-300">Evidence: {observed} kW measured against a {threshold} kW configured threshold.</p>}
                  {item.estimated_excess_cost_per_hour_mad != null && <p className="text-sm text-amber-300">Estimated excess-load cost: {item.estimated_excess_cost_per_hour_mad.toFixed(4)} MAD per hour at the configured tariff. This is not a projected saving.</p>}
                  <div className="flex flex-wrap gap-2">{isOpen ? <><Button size="sm" disabled={isUpdating} onClick={() => updateStatus(item, 'completed')} className="gap-2 bg-emerald-600 text-white hover:bg-emerald-500"><CheckCircle2 className="h-4 w-4" />Mark complete</Button><Button size="sm" variant="outline" disabled={isUpdating} onClick={() => updateStatus(item, 'dismissed')} className="gap-2 border-white/10 text-white hover:bg-white/5"><X className="h-4 w-4" />Dismiss</Button></> : <Button size="sm" variant="outline" disabled={isUpdating} onClick={() => updateStatus(item, 'open')} className="gap-2 border-white/10 text-white hover:bg-white/5"><RotateCcw className="h-4 w-4" />Reopen</Button>}</div>
                </CardContent>
              </Card>;
            })}
          </div>
        ) : <Card className="border-white/[0.06] bg-[#111827]/80"><CardContent className="flex min-h-44 flex-col items-center justify-center text-center"><CheckCircle2 className="mb-3 h-7 w-7 text-emerald-400" /><p className="font-medium text-white">No {showClosed ? '' : 'open '}evidence-backed actions</p><p className="mt-1 max-w-lg text-sm text-slate-400">Connect a meter, import readings, or run the labelled simulator. Alert rules create actions only when a measured condition needs attention.</p></CardContent></Card>}
      </div>
    </AppLayout>
  );
}
