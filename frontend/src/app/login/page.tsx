'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, Loader2, Lock, Mail, Zap } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { login, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace('/dashboard');
  }, [isAuthenticated, isLoading, router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login({ email, password });
      router.replace('/dashboard');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign in failed.');
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading || isAuthenticated) return <div className="flex min-h-screen items-center justify-center bg-[#080d16]"><Loader2 className="h-6 w-6 animate-spin text-cyan-400" /></div>;

  return (
    <main className="min-h-screen bg-[#080d16] text-slate-200">
      <header className="mx-auto flex h-16 max-w-7xl items-center justify-between border-b border-white/[0.08] px-5 sm:px-8"><Link href="/" className="flex items-center gap-2 text-white"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-600"><Zap className="h-5 w-5" /></span><span className="font-bold">EnergyAI</span></Link><Link href="/" className="text-sm text-slate-400 hover:text-white">Back to home</Link></header>
      <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-md items-center px-5 py-10">
        <section className="w-full border border-white/[0.1] bg-[#0d1420] p-6 sm:p-8">
          <h1 className="text-2xl font-bold text-white">Sign in</h1><p className="mt-2 text-sm text-slate-400">Open your private monitoring workspace.</p>
          {error ? <div className="mt-5 flex items-center gap-2 border border-red-400/25 bg-red-400/5 p-3 text-sm text-red-300"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div> : null}
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="space-y-2"><Label htmlFor="login-email">Email</Label><div className="relative"><Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="h-11 pl-10" /></div></div>
            <div className="space-y-2"><Label htmlFor="login-password">Password</Label><div className="relative"><Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required className="h-11 pl-10" /></div></div>
            <Button id="login-submit" type="submit" disabled={submitting} className="h-11 w-full">{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}{submitting ? 'Signing in' : 'Sign in'}</Button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-400">No account? <Link href="/register" className="font-medium text-cyan-300 hover:text-cyan-200">Create one</Link></p>
        </section>
      </div>
    </main>
  );
}
