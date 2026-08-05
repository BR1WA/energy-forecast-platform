'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Loader2, Mail } from 'lucide-react';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const response = await authApi.requestPasswordReset(email);
      setMessage(response.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Password reset is temporarily unavailable.');
    } finally {
      setSubmitting(false);
    }
  };

  return <main className="flex min-h-screen items-center justify-center bg-[#080d16] px-5 text-slate-200"><section className="w-full max-w-md border border-white/10 bg-[#0d1420] p-6 sm:p-8"><h1 className="text-2xl font-bold text-white">Reset your password</h1><p className="mt-2 text-sm text-slate-400">Enter your email. The response is intentionally the same for every address.</p>{message ? <div className="mt-5 border border-emerald-400/25 bg-emerald-400/5 p-3 text-sm text-emerald-200">{message}</div> : null}{error ? <div className="mt-5 border border-red-400/25 bg-red-400/5 p-3 text-sm text-red-200">{error}</div> : null}<form className="mt-6 space-y-4" onSubmit={submit}><div className="space-y-2"><Label htmlFor="reset-request-email">Email</Label><div className="relative"><Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"/><Input id="reset-request-email" className="pl-10" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)}/></div></div><Button className="w-full" disabled={submitting} type="submit">{submitting ? <Loader2 className="h-4 w-4 animate-spin"/> : null}Send reset instructions</Button></form><Link className="mt-6 block text-center text-sm text-cyan-300" href="/login">Back to sign in</Link></section></main>;
}
