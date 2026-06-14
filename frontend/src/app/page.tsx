'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Zap, Mail, Lock, ArrowRight, AlertCircle, ShieldCheck, Activity, Cpu, Sparkles, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';


export default function MarketingLandingPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // Mock live active power value for landing page animation
  const [mockPower, setMockPower] = useState(1.245);
  useEffect(() => {
    const interval = setInterval(() => {
      setMockPower(Number((1.1 + Math.random() * 0.4).toFixed(3)));
    }, 1500);
    return () => clearInterval(interval);
  }, []);

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
      <div className="absolute bottom-1/5 right-1/10 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl float-animation" style={{ animationDelay: '3s' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-cyan-500/5 rounded-full blur-3xl float-animation" style={{ animationDelay: '6s' }} />

      {/* Header / Navbar */}
      <header className="relative z-10 max-w-7xl mx-auto w-full px-6 h-20 flex items-center justify-between border-b border-white/[0.04]">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 shadow-lg shadow-blue-500/20">
            <Zap className="w-5 h-5 text-white animate-pulse" />
          </div>
          <span className="text-xl font-bold text-white tracking-tight">
            Energy<span className="gradient-text">AI</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 uppercase tracking-widest text-[9px] px-2 py-0.5">
            Smart Home Ready
          </Badge>
        </div>
      </header>

      {/* Main Marketing Hero & Sign In Section */}
      <main className="relative z-10 max-w-7xl mx-auto w-full px-6 py-12 md:py-20 flex-1 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* Left Side: Marketing Pitch */}
        <div className="lg:col-span-7 space-y-8 text-left">
          <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 px-3 py-1 text-xs font-semibold">
            Next-Gen Automated Power Management
          </Badge>
          
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-black text-white leading-none tracking-tight">
            Automated AI-Driven <br />
            <span className="gradient-text bg-gradient-to-r from-blue-400 via-cyan-400 to-emerald-400">
              Smart Energy Sync
            </span>
          </h1>

          <p className="text-base md:text-lg text-slate-400 max-w-2xl leading-relaxed">
            Unleash the power of deep learning on your residential grid. EnergyAI hooks directly to simulated Enedis Linky telemetry to deliver live monitoring, predict load demand curves 24h in advance, and shift loads to optimize electricity bill costs automatically.
          </p>

          {/* Key Features Quick Rows */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4">
            <div className="flex items-start gap-3 p-4 rounded-xl border border-white/[0.04] bg-white/[0.01]">
              <Activity className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-white">Live Telemetry Streams</h3>
                <p className="text-xs text-slate-400 mt-0.5">Real-time voltage, current draw, and device loads updating every 2s.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-xl border border-white/[0.04] bg-white/[0.01]">
              <Cpu className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-white">Deep PyTorch Forecasts</h3>
                <p className="text-xs text-slate-400 mt-0.5">PatchTST and SOTA models predict future peak hours with &gt;0.84 R².</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-xl border border-white/[0.04] bg-white/[0.01]">
              <Zap className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-white">Tariff-Aware Optimization</h3>
                <p className="text-xs text-slate-400 mt-0.5">Calculates peak vs Creuses tariff hours dynamically to shift load weight.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-xl border border-white/[0.04] bg-white/[0.01]">
              <ShieldCheck className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-white">Instant WebSocket Alarms</h3>
                <p className="text-xs text-slate-400 mt-0.5">Immediate notifications for anomalies and safety limit over-exposures.</p>
              </div>
            </div>
          </div>

          {/* Dynamic Live Telemetry Simulator widget */}
          <div className="pt-6">
            <div className="inline-flex items-center gap-6 p-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-md">
              <div className="relative w-16 h-16 flex items-center justify-center rounded-full border-2 border-dashed border-emerald-500/30">
                <div className="absolute inset-0 rounded-full border border-emerald-500/20 animate-ping" />
                <Zap className="w-6 h-6 text-emerald-400" />
              </div>
              <div className="text-left">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Linky Live Feed Simulator</p>
                <div className="flex items-baseline gap-1.5 mt-0.5">
                  <span className="text-2xl font-black text-white font-mono transition-all duration-300">{mockPower.toFixed(3)}</span>
                  <span className="text-xs font-bold text-slate-400">kW</span>
                </div>
                <p className="text-[10px] text-emerald-400 mt-0.5 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Streaming active telemetry
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Sign In Card */}
        <div className="lg:col-span-5 flex justify-center">
          <div className="w-full max-w-md animate-in fade-in duration-500">
            <Card className="glass-card border-white/[0.08] shadow-2xl shadow-black/50">
              <CardContent className="p-8">
                <div className="mb-6 text-left">
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-blue-400" />
                    Enter Dashboard
                  </h2>
                  <p className="text-sm text-slate-400 mt-1">
                    Sign in to your credentials to connect to your live grid.
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
                        Connecting...
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 justify-center w-full">
                        Connect Smart Meter
                        <ArrowRight className="w-4 h-4" />
                      </div>
                    )}
                  </Button>
                </form>

                <div className="mt-6 text-center">
                  <p className="text-xs text-slate-400">
                    Default credentials: <br />
                    <span className="font-mono text-slate-300">admin@energyforecast.com</span> / <span className="font-mono text-slate-300">admin123</span>
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 max-w-7xl mx-auto w-full px-6 h-16 flex items-center justify-between border-t border-white/[0.04] text-xs text-slate-500">
        <p>© 2026 EnergyAI. Master&apos;s PFE Residential Grid Automation Platform.</p>
        <p>Built with Next.js & PyTorch</p>
      </footer>
    </div>
  );
}
