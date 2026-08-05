'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import { authApi } from '@/lib/api';

export default function VerifyEmailPage() {
  const [state, setState] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [message, setMessage] = useState('Verifying your email...');

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token') || '';
    window.history.replaceState({}, '', window.location.pathname);
    if (!token) { setState('error'); setMessage('This verification link is missing its token.'); return; }
    authApi.confirmVerification(token)
      .then((response) => { setState('success'); setMessage(response.message); })
      .catch((caught) => { setState('error'); setMessage(caught instanceof Error ? caught.message : 'This verification link is invalid or expired.'); });
  }, []);

  return <main className="flex min-h-screen items-center justify-center bg-[#080d16] px-5 text-slate-200"><section className="w-full max-w-md border border-white/10 bg-[#0d1420] p-8 text-center">{state === 'verifying' ? <Loader2 className="mx-auto h-8 w-8 animate-spin text-cyan-300"/> : null}<h1 className="mt-4 text-2xl font-bold text-white">{state === 'success' ? 'Email verified' : state === 'error' ? 'Verification unavailable' : 'Verifying email'}</h1><p className="mt-3 text-sm text-slate-300">{message}</p>{state !== 'verifying' ? <Link className="mt-6 inline-block text-cyan-300" href={state === 'success' ? '/login' : '/verify-email/pending'}>{state === 'success' ? 'Continue to sign in' : 'Request another link'}</Link> : null}</section></main>;
}
