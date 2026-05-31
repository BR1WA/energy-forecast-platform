'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Zap, Mail, Lock, ArrowRight, AlertCircle } from 'lucide-react';

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
      <div className="flex items-center justify-center min-h-screen animated-gradient">
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-2 border-blue-500/20" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-500 animate-spin" />
        </div>
      </div>
    );
  }

  if (isAuthenticated) return null;

  return (
    <div className="relative flex items-center justify-center min-h-screen animated-gradient overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 grid-pattern opacity-30" />

      {/* Floating orbs */}
      <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl float-animation" />
      <div
        className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-cyan-500/5 rounded-full blur-3xl float-animation"
        style={{ animationDelay: '3s' }}
      />
      <div
        className="absolute top-1/2 right-1/3 w-48 h-48 bg-emerald-500/5 rounded-full blur-3xl float-animation"
        style={{ animationDelay: '6s' }}
      />

      {/* Login Card */}
      <div className="relative z-10 w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-700">
        {/* Logo Header */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 shadow-2xl shadow-blue-500/25 mb-4">
            <Zap className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Energy<span className="gradient-text">AI</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Smart Energy Management Platform
          </p>
        </div>

        <Card className="glass-card border-white/[0.08] shadow-2xl shadow-black/40">
          <CardContent className="p-8">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-white">Welcome back</h2>
              <p className="text-sm text-slate-400 mt-1">
                Sign in to your account to continue
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 mb-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm animate-in fade-in slide-in-from-top-2 duration-300">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="login-email" className="text-slate-300 text-sm">
                  Email
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="pl-10 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-slate-500 focus:border-blue-500/40 focus:ring-blue-500/20 h-11"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="login-password"
                  className="text-slate-300 text-sm"
                >
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
                className="w-full h-11 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-medium shadow-lg shadow-blue-500/20 transition-all duration-300 hover:shadow-blue-500/30 hover:scale-[1.01]"
              >
                {isSubmitting ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    Signing in...
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    Sign In
                    <ArrowRight className="w-4 h-4" />
                  </div>
                )}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-slate-400">
                Don&apos;t have an account?{' '}
                <Link
                  href="/register"
                  id="login-register-link"
                  className="text-blue-400 hover:text-blue-300 font-medium transition-colors duration-200"
                >
                  Create one
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <p className="text-center text-xs text-slate-600 mt-6">
          © 2025 EnergyAI. Powered by advanced forecasting models.
        </p>
      </div>
    </div>
  );
}
