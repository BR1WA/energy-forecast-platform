'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Loader2, Zap } from 'lucide-react';

import { PolicyLinks } from '@/components/policy-links';
import { systemApi } from '@/lib/api';
import type { LegalConfiguration } from '@/types';


export default function PublicPolicyLayout({
  title,
  children,
  contact = 'legal',
}: {
  title: string;
  children: React.ReactNode;
  contact?: 'legal' | 'support';
}) {
  const [configuration, setConfiguration] = useState<LegalConfiguration | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    systemApi.getLegalConfiguration()
      .then(setConfiguration)
      .catch(() => setFailed(true));
  }, []);

  const email = contact === 'support' ? configuration?.support_email : configuration?.contact_email;

  return (
    <main className="min-h-screen bg-[#080d16] text-slate-200">
      <header className="mx-auto flex h-16 max-w-5xl items-center justify-between border-b border-white/[0.08] px-5 sm:px-8">
        <Link className="flex items-center gap-2 text-white" href="/"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-600"><Zap className="h-5 w-5" /></span><span className="font-bold">EnergyAI</span></Link>
        <PolicyLinks />
      </header>
      <article className="mx-auto max-w-3xl px-6 py-12 sm:py-16">
        <h1 className="text-3xl font-bold text-white">{title}</h1>
        {configuration?.configured ? (
          <dl className="mt-5 grid gap-2 border-y border-white/10 py-4 text-sm text-slate-400 sm:grid-cols-2">
            <div><dt className="text-xs uppercase tracking-wide text-slate-500">Service owner</dt><dd className="mt-1 text-slate-300">{configuration.owner_name}</dd></div>
            <div><dt className="text-xs uppercase tracking-wide text-slate-500">Effective date</dt><dd className="mt-1 text-slate-300">{configuration.effective_date}</dd></div>
          </dl>
        ) : failed || configuration?.configured === false ? (
          <div className="mt-5 flex gap-2 border border-amber-400/25 bg-amber-400/5 p-3 text-sm text-amber-200"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />Public policy identity is unavailable. Deployed environments cannot start in this state.</div>
        ) : (
          <div className="mt-5 flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />Loading policy identity…</div>
        )}
        <div className="mt-8 space-y-7 text-sm leading-7 text-slate-300">{children}</div>
        {email ? <p className="mt-10 border-t border-white/10 pt-5 text-sm text-slate-400">Contact: <a className="text-cyan-300 hover:text-cyan-200" href={`mailto:${email}`}>{email}</a></p> : null}
      </article>
    </main>
  );
}
