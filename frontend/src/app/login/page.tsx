'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, Loader2, Lock, Mail, Zap } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth';
import { ApiError, authApi } from '@/lib/api';
import { requestGoogleCredential } from '@/lib/google';
import { PolicyLinks } from '@/components/policy-links';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [googleClientId, setGoogleClientId] = useState<string | null>(null);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);
  const [verificationRequired, setVerificationRequired] = useState(false);
  const { login, loginWithGoogle, user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace(user?.role === 'admin' ? '/admin' : '/dashboard');
  }, [user?.role, isAuthenticated, isLoading, router]);

  useEffect(() => {
    authApi.getCapabilities().then((capabilities) => {
      const configuredClient = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
      if (capabilities.google_auth_enabled && capabilities.google_client_id && configuredClient === capabilities.google_client_id) {
        setGoogleClientId(configuredClient);
      }
    }).catch(() => setGoogleClientId(null));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setVerificationRequired(false);
    setSubmitting(true);
    try {
      const signedInUser = await login({ email, password });
      router.replace(signedInUser.role === 'admin' ? '/admin' : '/dashboard');
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'email_verification_required') setVerificationRequired(true);
      setError(caught instanceof Error ? caught.message : 'Sign in failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const signInWithGoogle = async () => {
    if (!googleClientId) return;
    setGoogleSubmitting(true);
    setError('');
    try {
      const challenge = await authApi.googleChallenge();
      const credential = await requestGoogleCredential(googleClientId, challenge.nonce);
      const signedInUser = await loginWithGoogle(credential, challenge.state);
      router.replace(signedInUser.role === 'admin' ? '/admin' : '/dashboard');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Google sign-in failed.');
    } finally {
      setGoogleSubmitting(false);
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
          {verificationRequired ? <Link className="mt-3 block text-sm text-cyan-300" href={`/verify-email/pending?email=${encodeURIComponent(email.trim().toLowerCase())}`}>Resend verification email</Link> : null}
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="space-y-2"><Label htmlFor="login-email">Email</Label><div className="relative"><Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="h-11 pl-10" /></div></div>
            <div className="space-y-2"><Label htmlFor="login-password">Password</Label><div className="relative"><Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required className="h-11 pl-10" /></div></div>
            <Button id="login-submit" type="submit" disabled={submitting} className="h-11 w-full">{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}{submitting ? 'Signing in' : 'Sign in'}</Button>
          </form>
          <div className="mt-4 flex justify-end"><Link href="/forgot-password" className="text-sm text-cyan-300 hover:text-cyan-200">Forgot password?</Link></div>
          {googleClientId ? <Button type="button" variant="outline" disabled={googleSubmitting} onClick={signInWithGoogle} className="mt-5 h-11 w-full">{googleSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Continue with Google</Button> : null}
          <p className="mt-6 text-center text-sm text-slate-400">No account? <Link href="/register" className="font-medium text-cyan-300 hover:text-cyan-200">Create one</Link></p>
          <PolicyLinks className="mt-6 justify-center border-t border-white/10 pt-5" />
        </section>
      </div>
    </main>
  );
}
