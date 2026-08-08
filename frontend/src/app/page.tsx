'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Activity, ArrowRight, BellRing, ChartNoAxesCombined, FileSpreadsheet, ShieldCheck, Upload, Zap } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { authApi } from '@/lib/api';


const workflows = [
  { icon: Upload, title: 'Bring meter readings', text: 'Import a validated CSV, send authenticated push samples, or explicitly start the labelled simulator.' },
  { icon: ChartNoAxesCombined, title: 'Track every timeframe', text: 'Monitor Live, Today, Week, Month, Year, All history, or a custom period with source and freshness.' },
  { icon: BellRing, title: 'Act on measured evidence', text: 'High-load and missing-data rules create reviewable incidents and deterministic client actions.' },
];

export default function ProductLandingPage() {
  const { isAuthenticated } = useAuth();
  const [registrationAvailable, setRegistrationAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    if (isAuthenticated) return;
    authApi.getCapabilities()
      .then((capabilities) => setRegistrationAvailable(capabilities.email_delivery_enabled))
      .catch(() => setRegistrationAvailable(false));
  }, [isAuthenticated]);

  const primaryHref = isAuthenticated ? '/dashboard' : registrationAvailable ? '/register' : '/login';
  const primaryLabel = isAuthenticated ? 'Open dashboard' : registrationAvailable ? 'Create account' : 'Sign in';

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#080d16] text-slate-200">
      <header className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-2.5 text-white"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-600"><Zap className="h-5 w-5" /></span><span className="text-lg font-bold">EnergyAI</span></Link>
        <div className="flex items-center gap-2">
          {!isAuthenticated && registrationAvailable ? <Link href="/login"><Button variant="ghost" className="text-slate-200">Sign in</Button></Link> : null}
          <Link href={primaryHref}><Button>{primaryLabel}</Button></Link>
        </div>
      </header>

      <section className="relative h-[calc(100svh-8rem)] min-h-[520px] max-h-[760px] overflow-hidden border-y border-white/[0.08]">
        <Image src="/images/energyai-home-hero.png" alt="Home electricity meter and laptop displaying an energy chart" fill priority sizes="100vw" className="object-cover object-[62%_center]" />
        <div className="absolute inset-0 bg-black/45" />
        <div className="relative mx-auto flex h-full max-w-7xl items-center px-5 sm:px-8">
          <div className="max-w-2xl">
            <p className="mb-5 flex items-center gap-2 text-sm font-medium text-cyan-200"><Activity className="h-4 w-4" />Single-site electricity monitoring and forecasting</p>
            <h1 className="text-4xl font-bold leading-tight text-white sm:text-6xl">EnergyAI</h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-100 sm:text-lg">Monitor live and historical electricity use, understand tariff cost, and generate a persisted 24-hour hourly-energy forecast from your primary meter.</p>
            {!isAuthenticated && registrationAvailable === false ? <p className="mt-4 max-w-xl border-l-2 border-amber-300 pl-3 text-sm leading-6 text-amber-100">Public registration is currently unavailable. Existing verified users can still sign in; contact support if you need access.</p> : null}
            <div className="mt-8 flex flex-wrap gap-3"><Link href={primaryHref}><Button size="lg">{isAuthenticated ? 'Go to dashboard' : registrationAvailable ? 'Get started' : 'Sign in'}<ArrowRight className="h-4 w-4" /></Button></Link><Link href="#workflow"><Button size="lg" variant="outline" className="border-white/30 bg-black/25 text-white hover:bg-black/40">Product workflow</Button></Link></div>
          </div>
        </div>
      </section>

      <section id="workflow" className="mx-auto max-w-7xl px-5 py-14 sm:px-8">
        <div className="max-w-2xl"><h2 className="text-2xl font-bold text-white">One connected workflow</h2><p className="mt-3 leading-7 text-slate-400">Every chart, incident, action, forecast, and export traces back to the account&apos;s persisted meter records.</p></div>
        <div className="mt-8 grid gap-px overflow-hidden border border-white/[0.08] bg-white/[0.08] md:grid-cols-3">
          {workflows.map(({ icon: Icon, title, text }) => <article key={title} className="min-h-48 bg-[#0d1420] p-6"><Icon className="h-6 w-6 text-cyan-300" /><h3 className="mt-5 text-base font-semibold text-white">{title}</h3><p className="mt-3 text-sm leading-6 text-slate-400">{text}</p></article>)}
        </div>
      </section>

      <section className="border-y border-white/[0.08] bg-[#0d1420] px-5 py-14 sm:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[minmax(0,1fr)_420px] lg:items-start">
          <div><h2 className="text-2xl font-bold text-white">A fixed, honest forecast contract</h2><p className="mt-4 max-w-2xl leading-7 text-slate-400">The production path uses one versioned Global TFT artifact for the next 24 hourly kWh values. The weekly seasonal baseline appears only as a labelled fallback, never as hidden model output.</p></div>
          <div className="border-l-2 border-cyan-400/60 pl-5 text-sm"><div className="flex items-center gap-2 text-cyan-300"><FileSpreadsheet className="h-4 w-4" />Readiness gates</div><ul className="mt-4 space-y-2 text-slate-300"><li>336 hours from the primary meter</li><li>At least 95% observed coverage</li><li>No unresolved gap longer than 3 hours</li><li>Finite hourly energy values in kWh</li></ul></div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8"><div className="flex flex-col gap-5 border-l-2 border-emerald-400 bg-emerald-400/[0.04] p-6 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2 font-semibold text-white"><ShieldCheck className="h-5 w-5 text-emerald-400" />Start with your own records</div><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{isAuthenticated ? 'Your private site keeps meter readings, forecasts, and actions scoped to your account.' : registrationAvailable ? 'Registration creates one private site and primary meter. Setup captures timezone and tariff before the first import or push connection.' : 'Access is limited to existing verified users while public registration is unavailable.'}</p></div><Link href={primaryHref}><Button>{primaryLabel}<ArrowRight className="h-4 w-4" /></Button></Link></div></section>

      <footer className="border-t border-white/[0.06] px-5 py-7 text-center text-sm text-slate-500">EnergyAI, Master&apos;s PFE electricity monitoring platform.</footer>
    </main>
  );
}
