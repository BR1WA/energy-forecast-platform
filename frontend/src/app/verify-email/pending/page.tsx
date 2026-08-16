'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export default function VerificationPendingPage() {
  const [email, setEmail] = useState('');
  const [cooldown, setCooldown] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('Check your inbox for a single-use verification link.');

  useEffect(() => {
    const timer = window.setTimeout(
      () => setEmail(new URLSearchParams(window.location.search).get('email') || ''),
      0,
    );
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [cooldown]);

  const resend = async () => {
    if (!email || cooldown > 0) return;
    setSubmitting(true);
    try {
      const response = await authApi.resendVerification(email);
      setMessage(response.message);
      setCooldown(60);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Verification email is temporarily unavailable.');
    } finally {
      setSubmitting(false);
    }
  };

  return <main className="flex min-h-screen items-center justify-center bg-[#080d16] px-5 text-slate-200"><section className="w-full max-w-md border border-white/10 bg-[#0d1420] p-6 sm:p-8"><h1 className="text-2xl font-bold text-white">Verify your email</h1><p className="mt-3 text-sm text-slate-300">{message}</p><div className="mt-6 space-y-2"><Label htmlFor="verification-email">Email</Label><Input id="verification-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></div><Button className="mt-4 w-full" disabled={!email || submitting || cooldown > 0} onClick={resend}>{submitting ? <Loader2 className="h-4 w-4 animate-spin"/> : null}{cooldown > 0 ? `Resend available in ${cooldown}s` : 'Resend verification email'}</Button><Link className="mt-6 block text-center text-sm text-cyan-300" href="/login">Back to sign in</Link></section></main>;
}
