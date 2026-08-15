'use client';

import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, Download, MapPin, Radio, Upload, Wallet, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { ingestionApi, settingsApi, simulationApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import {
  MOROCCO_COUNTRY,
  MOROCCO_CURRENCY,
  MOROCCO_REGIONS,
  type MoroccoRegion,
} from '@/lib/morocco';

type DataPath = 'csv' | 'simulator' | 'push';

export default function SetupWizard() {
  const { refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [siteName, setSiteName] = useState('My site');
  const [region, setRegion] = useState<MoroccoRegion>('Casablanca-Settat');
  const [budget, setBudget] = useState('400');
  const [dataPath, setDataPath] = useState<DataPath>('csv');
  const [meterId, setMeterId] = useState<number | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ valid_rows: number; rejected_rows: number } | null>(null);

  useEffect(() => {
    ingestionApi.getMeters().then((meters) => setMeterId(meters[0]?.id ?? null)).catch(() => undefined);
  }, []);

  const previewCsv = async (file: File) => {
    if (!meterId) {
      toast.error('Your meter is still being prepared. Try again in a moment.');
      return;
    }
    setCsvFile(file);
    setPreview(null);
    try {
      const result = await ingestionApi.previewCsv(meterId, file);
      setPreview(result);
      if (result.valid_rows === 0) toast.error('This file has no valid readings.');
    } catch (error) {
      setCsvFile(null);
      toast.error(error instanceof Error ? error.message : 'Unable to check this CSV.');
    }
  };

  const completeSetup = async () => {
    if (dataPath === 'csv' && (!csvFile || !preview || preview.valid_rows === 0)) {
      toast.error('Choose a CSV with at least one valid reading before continuing.');
      return;
    }
    setSaving(true);
    try {
      await settingsApi.postSetup({
        site_name: siteName.trim() || 'My site',
        region,
        peak_rate: 1.1, off_peak_rate: 0.8, peak_start_hour: 6, peak_end_hour: 22,
        sensor_type: dataPath,
      });
      await settingsApi.setBudget({ monthly_budget_mad: Number(budget) || 0 });
      if (dataPath === 'csv' && csvFile && meterId) await ingestionApi.importCsv(meterId, csvFile);
      if (dataPath === 'simulator') await simulationApi.start();
      await refreshUser();
      toast.success('Your energy workspace is ready.');
      // A completed setup changes the root guard's routing state. A hard
      // navigation avoids a client-router race with that guard and guarantees
      // that a fresh account leaves the wizard after the simulator bootstrap.
      window.location.assign(dataPath === 'push' ? '/settings?tab=data' : '/dashboard');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to complete setup.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#0A0F1C] px-5 py-10 text-slate-200 sm:px-8">
      <div className="mx-auto max-w-2xl">
        <header className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-600 text-white"><Zap className="h-5 w-5" /></div>
          <div><h1 className="text-xl font-bold text-white">Set up your energy workspace</h1><p className="text-sm text-slate-400">Configure a site, tariff, budget, and a deliberate data source.</p></div>
        </header>
        <div className="mb-8 flex gap-2 text-xs text-slate-400"><span className={step >= 1 ? 'text-blue-300' : ''}>1 Site</span><span>/</span><span className={step >= 2 ? 'text-blue-300' : ''}>2 Budget</span><span>/</span><span className={step >= 3 ? 'text-blue-300' : ''}>3 Data</span></div>

        {step === 1 && <section className="space-y-5"><div className="flex items-center gap-2 text-blue-300"><MapPin className="h-5 w-5" /><h2 className="font-semibold">Moroccan site and tariff</h2></div><label className="block text-sm">Site name<input className="mt-2 w-full rounded-md border border-white/10 bg-[#111827] px-3 py-2" value={siteName} onChange={(event) => setSiteName(event.target.value)} /></label><label className="block text-sm">Region<select aria-label="Region" className="mt-2 w-full rounded-md border border-white/10 bg-[#111827] px-3 py-2" value={region} onChange={(event) => setRegion(event.target.value as MoroccoRegion)}>{MOROCCO_REGIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-md border border-white/10 bg-[#111827] p-3"><p className="text-xs text-slate-500">Country</p><p className="mt-1 text-sm font-medium text-white">{MOROCCO_COUNTRY}</p></div><div className="rounded-md border border-white/10 bg-[#111827] p-3"><p className="text-xs text-slate-500">Currency and timezone</p><p className="mt-1 text-sm font-medium text-white">{MOROCCO_CURRENCY} · Africa/Casablanca</p></div></div><p className="rounded-md border border-amber-400/15 bg-amber-400/[0.04] p-3 text-xs leading-5 text-amber-100/80">Provider is not collected because it does not change this app&apos;s calculation. Setup uses editable demonstration rates of 1.10 MAD/kWh peak and 0.80 MAD/kWh off-peak; displayed costs are estimates, not utility bills.</p><button className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white" onClick={() => setStep(2)}>Next <ArrowRight className="h-4 w-4" /></button></section>}

        {step === 2 && <section className="space-y-5"><div className="flex items-center gap-2 text-blue-300"><Wallet className="h-5 w-5" /><h2 className="font-semibold">Monthly budget</h2></div><label className="block text-sm">Budget in MAD<input className="mt-2 w-full rounded-md border border-white/10 bg-[#111827] px-3 py-2" type="number" min="0" value={budget} onChange={(event) => setBudget(event.target.value)} /></label><div className="flex gap-3"><button className="flex items-center gap-2 rounded-md border border-white/10 px-4 py-2 text-sm" onClick={() => setStep(1)}><ArrowLeft className="h-4 w-4" /> Back</button><button className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white" onClick={() => setStep(3)}>Next <ArrowRight className="h-4 w-4" /></button></div></section>}

        {step === 3 && <section className="space-y-5"><div className="flex items-center gap-2 text-blue-300"><Radio className="h-5 w-5" /><h2 className="font-semibold">Choose your first data source</h2></div><div className="grid gap-3 sm:grid-cols-3">{([{ id: 'csv', label: 'Import CSV', detail: 'Validate and import meter readings now.' }, { id: 'simulator', label: 'Simulator', detail: 'Create one hourly demo year so every forecast horizon is ready.' }, { id: 'push', label: 'Push API', detail: 'Connect a meter with its API key next.' }] as const).map((option) => <button key={option.id} onClick={() => setDataPath(option.id)} className={`min-h-28 rounded-md border p-3 text-left ${dataPath === option.id ? 'border-blue-500 bg-blue-500/10' : 'border-white/10 bg-[#111827]'}`}><p className="text-sm font-semibold text-white">{option.label}</p><p className="mt-2 text-xs text-slate-400">{option.detail}</p></button>)}</div>{dataPath === 'csv' && <div className="space-y-4 rounded-md border border-white/10 bg-[#111827] p-4"><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs leading-5 text-slate-400">Use your own UTF-8 meter export or download 14 days of forecast-ready demo history.</p><a className="inline-flex items-center gap-2 rounded-md border border-cyan-400/20 px-3 py-2 text-xs font-medium text-cyan-200 hover:bg-cyan-400/5" download href="/samples/forecast-ready"><Download className="h-4 w-4" />Download demo CSV</a></div><label className="flex cursor-pointer items-center gap-2 text-sm text-white"><Upload className="h-4 w-4" /> Choose UTF-8 CSV<input className="sr-only" type="file" accept=".csv,text/csv" onChange={(event) => event.target.files?.[0] && previewCsv(event.target.files[0])} /></label>{preview && <p className="mt-3 text-xs text-slate-300"><CheckCircle2 className="mr-1 inline h-3.5 w-3.5 text-emerald-400" />{preview.valid_rows} valid rows, {preview.rejected_rows} rejected. The import uses the validated rows only.</p>}</div>}<div className="flex gap-3"><button className="flex items-center gap-2 rounded-md border border-white/10 px-4 py-2 text-sm" onClick={() => setStep(2)}><ArrowLeft className="h-4 w-4" /> Back</button><button className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60" onClick={completeSetup} disabled={saving}>{saving ? 'Completing...' : dataPath === 'push' ? 'Continue to connection' : 'Complete setup'}</button></div></section>}
      </div>
    </main>
  );
}
