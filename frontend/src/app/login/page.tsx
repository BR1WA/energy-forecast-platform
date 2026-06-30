'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Zap, Mail, Lock, ArrowRight, AlertCircle, Sparkles, Loader2 } from 'lucide-react';
import Link from 'next/link';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login({ email, password });
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0A0F1C]" suppressHydrationWarning>
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-2 border-blue-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin" />
        </div>
      </div>
    );
  }

  if (isAuthenticated) return null;

  return (
    <div className="relative min-h-screen bg-[#0A0F1C] text-slate-200 overflow-x-hidden font-sans flex flex-col justify-between">
      {/* Background Decorative Grid */}
      <div className="absolute inset-0 grid-pattern opacity-10 pointer-events-none" />

      {/* Floating Gradient Orbs */}
      <div className="absolute top-1/10 left-1/10 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl float-animation" />
      <div className="absolute bottom-1/5 right-1/10 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl float-animation" style={{ animationDelay: '3s' }} />

      {/* Header */}
      <header className="relative z-10 max-w-7xl mx-auto w-full px-6 h-20 flex items-center justify-between border-b border-white/[0.04]">
        <Link href="/" className="flex items-center gap-3 cursor-pointer group">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 shadow-lg shadow-blue-500/20 group-hover:scale-105 transition-transform">
            <Zap className="w-5 h-5 text-white animate-pulse" />
          </div>
          <span className="text-xl font-bold text-white tracking-tight">
            Energy<span className="gradient-text">AI</span>
          </span>
        </Link>
        <div>
          <Link href="/">
            <Button variant="ghost" className="text-slate-400 hover:text-white hover:bg-white/5 cursor-pointer">
              Back to Home
            </Button>
          </Link>
        </div>
      </header>

      {/* Login Card Container */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md animate-in fade-in duration-500">
          <Card className="glass-card border-white/[0.08] shadow-2xl shadow-black/50">
            <CardContent className="p-8">
              <div className="mb-6 text-left">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-blue-400 animate-pulse" />
                  Connect Smart Meter
                </h2>
                <p className="text-sm text-slate-400 mt-1">
                  Sign in to connect to your live utility grid feed.
                </p>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 mb-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm animate-in fade-in slide-in-from-top-2 duration-300 text-left">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4 text-left">
                <div className="space-y-2">
                  <Label htmlFor="login-email" className="text-slate-300 text-sm">
                    Email Address
                  </Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <Input
                      id="login-email"
                      type="email"
                      placeholder="admin@energyforecast.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      className="pl-10 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-slate-500 focus:border-blue-500/40 focus:ring-blue-500/20 h-11"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="login-password" className="text-slate-300 text-sm">
                    Password
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <Input
                      id="login-password"
                      type="password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="pl-10 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-slate-500 focus:border-blue-500/40 focus:ring-blue-500/20 h-11"
                    />
                  </div>
                </div>

                <Button
                  id="login-submit"
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full h-11 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-medium shadow-lg shadow-blue-500/20 transition-all duration-300 hover:shadow-blue-500/30 hover:scale-[1.01] cursor-pointer mt-2"
                >
                  {isSubmitting ? (
                    <div className="flex items-center gap-2 justify-center w-full">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Authenticating...
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 justify-center w-full">
                      Connect Smart Meter
                      <ArrowRight className="w-4 h-4" />
                    </div>
                  )}
                </Button>
              </form>

              <div className="mt-6 text-center space-y-3">
                <p className="text-sm text-slate-400">
                  Don&apos;t have an account?{' '}
                  <Link
                    href="/register"
                    id="login-register-link"
                    className="text-blue-400 hover:text-blue-300 font-medium transition-colors duration-200"
                  >
                    Sign up
                  </Link>
                </p>

              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 max-w-7xl mx-auto w-full px-6 h-16 flex items-center justify-between border-t border-white/[0.04] text-xs text-slate-500">
        <p>© 2026 EnergyAI. Master&apos;s PFE Residential Grid Automation Platform.</p>
        <p>Secure SSL Authentication</p>
      </footer>
    </div>
  );
}
