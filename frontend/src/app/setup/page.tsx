'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, MapPin, Wallet, Zap } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { settingsApi } from '@/lib/api';

export default function SetupWizard() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [region, setRegion] = useState('Casablanca-Settat');
  const [provider, setProvider] = useState('ONEE');
  const [budget, setBudget] = useState('400');

  const completeSetup = async () => {
    setSaving(true);
    try {
      await settingsApi.postSetup({ country: 'Morocco', region, electricity_provider: provider, currency: 'MAD', peak_rate: 1.1, off_peak_rate: 0.8, peak_start_hour: 6, peak_end_hour: 22, sensor_type: 'simulator', sensor_api_url: null });
      await settingsApi.setBudget({ monthly_budget_mad: Number(budget) || 0 });
      await refreshUser();
      toast.success('Your energy workspace is ready.');
      router.push('/dashboard');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to complete setup.');
    } finally {
      setSaving(false);
    }
  };

  return <main className="min-h-screen bg-[#0A0F1C] px-6 py-12 text-slate-200"><div className="mx-auto max-w-xl"><div className="mb-10 flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500 text-white"><Zap className="h-5 w-5" /></div><div><h1 className="text-xl font-bold text-white">Set up your site</h1><p className="text-sm text-slate-400">A couple of details and you are ready to monitor energy.</p></div></div>{step === 1 ? <section className="space-y-5"><div className="flex items-center gap-2 text-blue-300"><MapPin className="h-5 w-5" /><h2 className="font-semibold">Location and provider</h2></div><label className="block text-sm">Region<input className="mt-2 w-full rounded-md border border-white/10 bg-[#111827] px-3 py-2" value={region} onChange={(event) => setRegion(event.target.value)} /></label><label className="block text-sm">Electricity provider<input className="mt-2 w-full rounded-md border border-white/10 bg-[#111827] px-3 py-2" value={provider} onChange={(event) => setProvider(event.target.value)} /></label><button className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white" onClick={() => setStep(2)}>Next <ArrowRight className="h-4 w-4" /></button></section> : <section className="space-y-5"><div className="flex items-center gap-2 text-blue-300"><Wallet className="h-5 w-5" /><h2 className="font-semibold">Monthly budget</h2></div><label className="block text-sm">Budget in MAD<input className="mt-2 w-full rounded-md border border-white/10 bg-[#111827] px-3 py-2" type="number" min="0" value={budget} onChange={(event) => setBudget(event.target.value)} /></label><div className="flex gap-3"><button className="rounded-md border border-white/10 px-4 py-2 text-sm" onClick={() => setStep(1)}>Back</button><button className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white" onClick={completeSetup} disabled={saving}>{saving ? 'Saving...' : 'Complete setup'}</button></div></section>}</div></main>;
}
