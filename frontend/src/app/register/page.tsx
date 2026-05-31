'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Zap, Mail, Lock, User, ArrowRight, AlertCircle } from 'lucide-react';

export default function RegisterPage() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      await register({ email, password, full_name: fullName });
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative flex items-center justify-center min-h-screen animated-gradient overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 grid-pattern opacity-30" />
      <div className="absolute top-1/3 left-1/3 w-72 h-72 bg-cyan-500/5 rounded-full blur-3xl float-animation" />
      <div
        className="absolute bottom-1/3 right-1/4 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl float-animation"
        style={{ animationDelay: '4s' }}
      />

      {/* Register Card */}
      <div className="relative z-10 w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-700">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-500 shadow-2xl shadow-cyan-500/25 mb-4">
            <Zap className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Join <span className="gradient-text">EnergyAI</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Create your account to get started
          </p>
        </div>

        <Card className="glass-card border-white/[0.08] shadow-2xl shadow-black/40">
          <CardContent className="p-8">
            {error && (
              <div className="flex items-center gap-2 p-3 mb-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm animate-in fade-in slide-in-from-top-2 duration-300">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="register-name" className="text-slate-300 text-sm">
                  Full Name
                </Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <Input
                    id="register-name"
                    type="text"
                    placeholder="John Doe"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                    className="pl-10 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-slate-500 focus:border-blue-500/40 focus:ring-blue-500/20 h-11"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="register-email"
                  className="text-slate-300 text-sm"
                >
                  Email
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <Input
                    id="register-email"
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
                  htmlFor="register-password"
                  className="text-slate-300 text-sm"
                >
                  Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <Input
                    id="register-password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="pl-10 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-slate-500 focus:border-blue-500/40 focus:ring-blue-500/20 h-11"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="register-confirm"
                  className="text-slate-300 text-sm"
                >
                  Confirm Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <Input
                    id="register-confirm"
                    type="password"
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    className="pl-10 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-slate-500 focus:border-blue-500/40 focus:ring-blue-500/20 h-11"
                  />
                </div>
              </div>

              <Button
                id="register-submit"
                type="submit"
                disabled={isSubmitting}
                className="w-full h-11 bg-gradient-to-r from-cyan-600 to-blue-500 hover:from-cyan-500 hover:to-blue-400 text-white font-medium shadow-lg shadow-cyan-500/20 transition-all duration-300 hover:shadow-cyan-500/30 hover:scale-[1.01]"
              >
                {isSubmitting ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    Creating account...
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    Create Account
                    <ArrowRight className="w-4 h-4" />
                  </div>
                )}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-slate-400">
                Already have an account?{' '}
                <Link
                  href="/"
                  id="register-login-link"
                  className="text-blue-400 hover:text-blue-300 font-medium transition-colors duration-200"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
