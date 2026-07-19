'use client';

import Link from 'next/link';
import { Activity, ArrowRight, BellRing, ChartNoAxesCombined, FileSpreadsheet, ShieldCheck, Sparkles, Upload, Zap } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';

const workflows = [
  { icon: Upload, title: 'Bring your readings', text: 'Validate and import a UTF-8 CSV, send authenticated push samples, or use the clearly labelled simulator.' },
  { icon: ChartNoAxesCombined, title: 'Understand cost and usage', text: 'Review source-labelled consumption history, interval-based tariff cost, and monthly budget progress.' },
  { icon: BellRing, title: 'Act on evidence', text: 'High-load and missing-data rules create client actions with the measured values and calculation that produced them.' },
];

export default function MarketingLandingPage() {
  const { isAuthenticated } = useAuth();
  const primaryHref = isAuthenticated ? '/dashboard' : '/register';

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#0A0F1C] text-slate-200">
      <header className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between border-b border-white/[0.06] px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-2.5 text-white"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600"><Zap className="h-5 w-5" /></span><span className="text-lg font-bold">EnergyAI</span></Link>
        <div className="flex items-center gap-2">
          {!isAuthenticated && <Link href="/login"><Button variant="ghost" className="text-slate-200 hover:bg-white/[0.06] hover:text-white">Sign in</Button></Link>}
          <Link href={primaryHref}><Button className="bg-blue-600 text-white hover:bg-blue-500">{isAuthenticated ? 'Open dashboard' : 'Create workspace'}</Button></Link>
        </div>
      </header>

      <section className="relative border-b border-white/[0.06] px-5 py-20 sm:px-8 sm:py-28">
        <div className="pointer-events-none absolute inset-0 opacity-20 [background-image:linear-gradient(rgba(96,165,250,.14)_1px,transparent_1px),linear-gradient(90deg,rgba(96,165,250,.14)_1px,transparent_1px)] [background-size:40px_40px]" />
        <div className="relative mx-auto max-w-5xl">
          <p className="mb-5 flex items-center gap-2 text-sm font-medium text-cyan-300"><Activity className="h-4 w-4" />Measured energy intelligence for homes and small sites</p>
          <h1 className="max-w-4xl text-4xl font-bold leading-tight text-white sm:text-6xl">EnergyAI</h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300">Connect real or simulated meter data, understand energy cost, run a validated 24-hour forecast, and track actions that have a recorded source and calculation.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href={primaryHref}><Button size="lg" className="gap-2 bg-blue-600 text-white hover:bg-blue-500">{isAuthenticated ? 'Go to dashboard' : 'Get started'}<ArrowRight className="h-4 w-4" /></Button></Link>
            <Link href="#workflow"><Button size="lg" variant="outline" className="border-white/15 text-white hover:bg-white/[0.06]">See workflow</Button></Link>
          </div>
          <div className="mt-12 grid gap-3 border-l border-cyan-400/50 pl-5 text-sm text-slate-300 sm:grid-cols-3">
            <span>CSV import</span><span>Authenticated push API</span><span>Labelled simulator</span>
          </div>
        </div>
      </section>

      <section id="workflow" className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <div className="max-w-2xl"><h2 className="text-2xl font-bold text-white">A connected client workflow</h2><p className="mt-3 text-slate-400">The PFE release deliberately avoids remote device control, unvalidated long-horizon forecasts, and invented savings claims.</p></div>
        <div className="mt-8 grid gap-px overflow-hidden border border-white/[0.08] bg-white/[0.08] md:grid-cols-3">
          {workflows.map(({ icon: Icon, title, text }) => <article key={title} className="min-h-52 bg-[#0D1321] p-6"><Icon className="h-6 w-6 text-cyan-300" /><h3 className="mt-6 text-lg font-semibold text-white">{title}</h3><p className="mt-3 text-sm leading-6 text-slate-400">{text}</p></article>)}
        </div>
      </section>

      <section className="border-y border-white/[0.06] bg-[#0D1321] px-5 py-16 sm:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-2 lg:items-center">
          <div><h2 className="text-2xl font-bold text-white">Forecasting with an honest contract</h2><p className="mt-4 leading-7 text-slate-400">The application serves three compatible 24-hour artifacts: PatchTST, CNN-BiLSTM, and SOTA Hybrid. A forecast includes its model identity and input provenance. It is presented as a point forecast until calibrated uncertainty and client-specific backtesting are available.</p></div>
          <div className="border border-white/[0.08] bg-black/15 p-5 text-sm"><div className="flex items-center gap-2 text-cyan-300"><FileSpreadsheet className="h-4 w-4" />Forecast prerequisites</div><ul className="mt-4 space-y-2 text-slate-300"><li>Compatible 96-reading input window</li><li>Validated artifact and preprocessing pipeline</li><li>Persisted model and input provenance</li></ul></div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8"><div className="flex flex-col gap-5 border-l-2 border-emerald-400 bg-emerald-400/[0.04] p-6 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2 font-semibold text-white"><ShieldCheck className="h-5 w-5 text-emerald-400" />Start from data you can trust</div><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">Create a site, configure its tariff, then import data or connect a meter. The dashboard only displays facts backed by that account&apos;s records.</p></div><Link href={primaryHref}><Button className="gap-2 bg-emerald-600 text-white hover:bg-emerald-500">{isAuthenticated ? 'Open dashboard' : 'Create workspace'}<Sparkles className="h-4 w-4" /></Button></Link></div></section>

      <footer className="border-t border-white/[0.06] px-5 py-7 text-center text-sm text-slate-500">EnergyAI, Master&apos;s PFE energy intelligence platform. CSV, Push API, and Simulator.</footer>
    </main>
  );
}
