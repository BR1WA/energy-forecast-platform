'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export default function ResetPasswordPage() {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [state, setState] = useState<'ready' | 'submitting' | 'success' | 'error'>('ready');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get('token') || '';
    window.history.replaceState({}, '', window.location.pathname);
    setToken(value);
    if (!value) { setState('error'); setMessage('This reset link is missing its token.'); }
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (password.length < 8) { setMessage('Password must be at least 8 characters.'); setState('error'); return; }
    if (password !== confirmation) { setMessage('Passwords do not match.'); setState('error'); return; }
    setState('submitting');
    try {
      const response = await authApi.confirmPasswordReset(token, password);
      setMessage(response.message);
      setState('success');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'The reset link is invalid or expired.');
      setState('error');
    }
  };

  return <main className="flex min-h-screen items-center justify-center bg-[#080d16] px-5 text-slate-200"><section className="w-full max-w-md border border-white/10 bg-[#0d1420] p-6 sm:p-8"><h1 className="text-2xl font-bold text-white">Choose a new password</h1>{message ? <div className={`mt-5 border p-3 text-sm ${state === 'success' ? 'border-emerald-400/25 bg-emerald-400/5 text-emerald-200' : 'border-red-400/25 bg-red-400/5 text-red-200'}`}>{message}</div> : null}{state === 'success' ? <Link className="mt-6 block text-center text-cyan-300" href="/login">Sign in with your new password</Link> : <form className="mt-6 space-y-4" onSubmit={submit}><div className="space-y-2"><Label htmlFor="new-password">New password</Label><Input id="new-password" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)}/></div><div className="space-y-2"><Label htmlFor="confirm-new-password">Confirm password</Label><Input id="confirm-new-password" type="password" autoComplete="new-password" minLength={8} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)}/></div><Button className="w-full" disabled={!token || state === 'submitting'} type="submit">{state === 'submitting' ? <Loader2 className="h-4 w-4 animate-spin"/> : null}Reset password</Button></form>}</section></main>;
}
