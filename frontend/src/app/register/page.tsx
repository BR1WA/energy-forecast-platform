'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, Loader2, Lock, Mail, User, Zap } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth';
import { authApi } from '@/lib/api';
import { requestGoogleCredential } from '@/lib/google';
import { PolicyLinks } from '@/components/policy-links';

export default function RegisterPage() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [registrationAvailable, setRegistrationAvailable] = useState<boolean | null>(null);
  const [googleClientId, setGoogleClientId] = useState<string | null>(null);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);
  const { register, loginWithGoogle } = useAuth();
  const router = useRouter();

  useEffect(() => {
    authApi.getCapabilities()
      .then((capabilities) => {
        setRegistrationAvailable(capabilities.email_delivery_enabled);
        const configuredClient = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
        if (capabilities.google_auth_enabled && capabilities.google_client_id && configuredClient === capabilities.google_client_id) {
          setGoogleClientId(configuredClient);
        }
      })
      .catch(() => {
        setRegistrationAvailable(false);
        setGoogleClientId(null);
      });
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (password.length < 12) { setError('Password must be at least 12 characters.'); return; }
    if (password !== confirmPassword) { setError('Passwords do not match.'); return; }
    setSubmitting(true);
    try {
      await register({ email, password, full_name: fullName });
      router.replace(`/verify-email/pending?email=${encodeURIComponent(email.trim().toLowerCase())}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Account creation failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const signUpWithGoogle = async () => {
    if (!googleClientId) return;
    setGoogleSubmitting(true);
    setError('');
    try {
      const challenge = await authApi.googleChallenge();
      const credential = await requestGoogleCredential(googleClientId, challenge.nonce);
      const signedInUser = await loginWithGoogle(credential, challenge.state);
      router.replace(signedInUser.role === 'admin' ? '/admin' : signedInUser.is_setup_complete ? '/dashboard' : '/setup');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Google signup failed.');
    } finally {
      setGoogleSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#080d16] text-slate-200">
      <header className="mx-auto flex h-16 max-w-7xl items-center justify-between border-b border-white/[0.08] px-5 sm:px-8"><Link href="/" className="flex items-center gap-2 text-white"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-600"><Zap className="h-5 w-5" /></span><span className="font-bold">EnergyAI</span></Link><Link href="/login" className="text-sm text-slate-400 hover:text-white">Sign in</Link></header>
      <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-md items-center px-5 py-10">
        <section className="w-full border border-white/[0.1] bg-[#0d1420] p-6 sm:p-8">
          <h1 className="text-2xl font-bold text-white">Create your account</h1><p className="mt-2 text-sm text-slate-400">Create your identity first. After email verification, setup creates a Morocco-based private site and asks you to select its region.</p>
          {registrationAvailable === false ? <div className="mt-5 border border-amber-400/25 bg-amber-400/5 p-3 text-sm text-amber-200">{googleClientId ? 'Email/password registration is temporarily unavailable. You can still continue securely with Google.' : 'Registration is temporarily unavailable while email delivery is disabled.'}</div> : null}
          {error ? <div className="mt-5 flex items-center gap-2 border border-red-400/25 bg-red-400/5 p-3 text-sm text-red-300"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div> : null}
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="space-y-2"><Label htmlFor="register-name">Full name</Label><div className="relative"><User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="register-name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} required minLength={1} className="h-11 pl-10" /></div></div>
            <div className="space-y-2"><Label htmlFor="register-email">Email</Label><div className="relative"><Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="register-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="h-11 pl-10" /></div></div>
            <div className="space-y-2"><Label htmlFor="register-password">Password</Label><div className="relative"><Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="register-password" type="password" autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required className="h-11 pl-10" /></div><p className="text-xs text-slate-500">At least 12 characters</p></div>
            <div className="space-y-2"><Label htmlFor="register-confirm">Confirm password</Label><div className="relative"><Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input id="register-confirm" type="password" autoComplete="new-password" minLength={12} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required className="h-11 pl-10" /></div></div>
            <Button id="register-submit" type="submit" disabled={submitting || registrationAvailable !== true} className="h-11 w-full">{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}{submitting ? 'Creating account' : registrationAvailable === null ? 'Checking availability' : 'Create account'}</Button>
          </form>
          {googleClientId ? <><div className="my-5 flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-slate-500"><span className="h-px flex-1 bg-white/10" /><span>or</span><span className="h-px flex-1 bg-white/10" /></div><Button type="button" variant="outline" disabled={googleSubmitting} onClick={signUpWithGoogle} className="h-11 w-full">{googleSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Continue with Google</Button></> : null}
          <p className="mt-6 text-center text-sm text-slate-400">Already registered? <Link id="register-login-link" href="/login" className="font-medium text-cyan-300 hover:text-cyan-200">Sign in</Link></p>
          <PolicyLinks className="mt-6 justify-center border-t border-white/10 pt-5" />
        </section>
      </div>
    </main>
  );
}
