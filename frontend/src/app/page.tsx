'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Zap, ArrowRight, ShieldCheck, Activity, Cpu, Sparkles, Database, Layers, CheckCircle2, TrendingUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

// Helper component for Scroll Reveal animations
function ScrollReveal({ children, className = "", style }: { children: React.ReactNode, className?: string, style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.08 }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => {
      if (ref.current) {
        observer.unobserve(ref.current);
      }
    };
  }, []);

  return (
    <div
      ref={ref}
      style={style}
      className={cn(
        "transition-all duration-1000 ease-out transform",
        isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-12",
        className
      )}
    >
      {children}
    </div>
  );
}

// Simulated floating electricity waves background
function DynamicGridWave() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-20 z-0">
      <svg className="absolute w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="grid-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0" />
            <stop offset="50%" stopColor="#06B6D4" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M -100 250 C 300 50, 600 450, 1000 250 C 1400 50, 1700 350, 2200 200"
          fill="none"
          stroke="url(#grid-grad)"
          strokeWidth="3.5"
          strokeDasharray="1200"
          strokeDashoffset="1200"
          className="animate-wave-flow"
        />
        <path
          d="M -100 350 C 250 500, 700 150, 1100 350 C 1500 550, 1800 250, 2200 450"
          fill="none"
          stroke="url(#grid-grad)"
          strokeWidth="2"
          strokeDasharray="1200"
          strokeDashoffset="1200"
          className="animate-wave-flow"
          style={{ animationDelay: '-5s', animationDuration: '10s' }}
        />
      </svg>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes waveFlow {
          0% { stroke-dashoffset: 2400; }
          100% { stroke-dashoffset: 0; }
        }
        .animate-wave-flow {
          animation: waveFlow 12s linear infinite;
        }
      ` }} />
    </div>
  );
}

export default function MarketingLandingPage() {
  const { isAuthenticated } = useAuth();
  
  // Ticking metrics for active power simulator
  const [mockPower, setMockPower] = useState(1.245);
  useEffect(() => {
    const interval = setInterval(() => {
      setMockPower(Number((1.05 + Math.random() * 0.55).toFixed(3)));
    }, 1800);
    return () => clearInterval(interval);
  }, []);

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
        <div className="flex items-center gap-3">
          <Badge className="hidden md:inline-flex bg-emerald-500/10 text-emerald-400 border-emerald-500/20 uppercase tracking-widest text-[9px] px-2 py-0.5">
            Smart Home Ready
          </Badge>
          {isAuthenticated ? (
            <Link href="/dashboard">
              <Button className="bg-blue-600 hover:bg-blue-500 text-white h-9 px-4 rounded-lg cursor-pointer text-xs font-semibold shadow-lg shadow-blue-500/10">
                Enter Dashboard
              </Button>
            </Link>
          ) : (
            <>
              <Link href="/login">
                <Button className="bg-white/5 hover:bg-white/10 text-white border border-white/10 h-9 px-4 rounded-lg cursor-pointer text-xs font-semibold">
                  Sign In
                </Button>
              </Link>
              <Link href="/register">
                <Button className="bg-blue-600 hover:bg-blue-500 text-white h-9 px-4 rounded-lg cursor-pointer text-xs font-semibold shadow-lg shadow-blue-500/10">
                  Sign Up
                </Button>
              </Link>
            </>
          )}
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 max-w-7xl mx-auto w-full px-6 pt-16 pb-24 flex-1 flex flex-col justify-center items-center text-center">
        <DynamicGridWave />

        <div className="max-w-4xl space-y-8 animate-in fade-in slide-in-from-top-4 duration-700 relative z-10">
          <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 px-3 py-1 text-xs font-semibold tracking-wide">
            Next-Gen Automated Power Management
          </Badge>
          
          <h1 className="text-4xl sm:text-6xl md:text-7xl font-black text-white leading-tight tracking-tight">
            Automated AI-Driven <br />
            <span className="gradient-text bg-gradient-to-r from-blue-400 via-cyan-400 to-emerald-400">
              Smart Energy Sync
            </span>
          </h1>

          <p className="text-base sm:text-xl text-slate-400 max-w-3xl mx-auto leading-relaxed">
            Hook your home directly to live smart meter streams. Leverage deep learning algorithms to predict your load curve up to 1 Month in advance (24h, 1-Week, and 1-Month horizons) and shift energy usage to low-tariff hours automatically.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
            <Link href={isAuthenticated ? "/dashboard" : "/register"}>
              <Button className="h-12 px-8 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all duration-300 hover:scale-[1.02] cursor-pointer rounded-xl text-sm flex items-center gap-2">
                {isAuthenticated ? 'Go to Dashboard' : 'Connect Smart Meter'}
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
            <a href="#details">
              <Button variant="ghost" className="h-12 px-6 text-slate-400 hover:text-white hover:bg-white/5 cursor-pointer rounded-xl text-sm font-semibold">
                Explore Features
              </Button>
            </a>
          </div>

          {/* Dynamic Live Ticker Widget */}
          <div className="pt-8 flex justify-center">
            <div className="inline-flex items-center gap-6 p-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-md shadow-2xl">
              <div className="relative w-14 h-14 flex items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/5">
                <div className="absolute inset-0 rounded-full border border-emerald-500/20 animate-ping" />
                <Zap className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="text-left">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Linky Simulated Stream</p>
                <div className="flex items-baseline gap-1 mt-0.5">
                  <span className="text-2xl font-black text-white font-mono transition-all duration-300">{mockPower.toFixed(3)}</span>
                  <span className="text-xs font-bold text-slate-400">kW</span>
                </div>
                <p className="text-[10px] text-emerald-400 mt-0.5 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Streaming live measurements
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Feature Section with Scroll Reveal */}
      <section id="details" className="relative z-10 max-w-7xl mx-auto w-full px-6 py-24 border-t border-white/[0.04]">
        <ScrollReveal className="text-center space-y-4 mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            Comprehensive Smart Integration
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-sm sm:text-base">
            Engineered to automate local residential power optimization using advanced machine learning model parameters.
          </p>
        </ScrollReveal>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <ScrollReveal className="transition-all duration-300 hover:translate-y-[-4px]">
            <div className="h-full p-6 rounded-2xl border border-white/[0.06] bg-white/[0.01] hover:bg-white/[0.03] transition-colors space-y-4 text-left">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <Activity className="w-5 h-5 text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Live Telemetry</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Connect directly to utility smart meters. Monitor active/reactive load draws, electrical voltage shifts, and sub-metering systems updating dynamically every 2 seconds.
              </p>
            </div>
          </ScrollReveal>

          <ScrollReveal className="transition-all duration-300 hover:translate-y-[-4px]" style={{ animationDelay: '150ms' }}>
            <div className="h-full p-6 rounded-2xl border border-white/[0.06] bg-white/[0.01] hover:bg-white/[0.03] transition-colors space-y-4 text-left">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">PyTorch Predictors</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Run advanced forecasting using PatchTST, iTransformer, and SOTA Hybrid time-series models. Predict load curves up to 1 Month ahead with validated R² accuracy exceeding 0.84.
              </p>
            </div>
          </ScrollReveal>

          <ScrollReveal className="transition-all duration-300 hover:translate-y-[-4px]" style={{ animationDelay: '300ms' }}>
            <div className="h-full p-6 rounded-2xl border border-white/[0.06] bg-white/[0.01] hover:bg-white/[0.03] transition-colors space-y-4 text-left">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <Zap className="w-5 h-5 text-amber-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Tariff Optimizer</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Reduce utility expenditures. Automatically calculate EDF Peak (Pleines) vs. Off-Peak (Creuses) hour structures to schedule load shifts dynamically.
              </p>
            </div>
          </ScrollReveal>

          <ScrollReveal className="transition-all duration-300 hover:translate-y-[-4px]" style={{ animationDelay: '450ms' }}>
            <div className="h-full p-6 rounded-2xl border border-white/[0.06] bg-white/[0.01] hover:bg-white/[0.03] transition-colors space-y-4 text-left">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">WebSocket Alerts</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Never overload your grid. Instant warnings are broadcast directly to the interface through secure WebSocket connections whenever demand violates custom safe thresholds.
              </p>
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* Model Spec Showcases */}
      <section className="relative z-10 max-w-7xl mx-auto w-full px-6 py-20 border-t border-white/[0.04] bg-gradient-to-b from-transparent to-white/[0.01]">
        <ScrollReveal className="text-center mb-16 space-y-4">
          <h2 className="text-3xl font-bold text-white tracking-tight">
            Deep Learning Core Models
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-sm">
            Evaluate time-series predictions using three highly optimized algorithms, integrated cleanly into the platform pipeline.
          </p>
        </ScrollReveal>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* iTransformer */}
          <ScrollReveal className="glass-card border-white/[0.06] p-8 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Badge className="bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono text-[10px]">
                  Long-Term Transformer
                </Badge>
                <span className="text-slate-500 text-xs font-semibold">v1.0.0</span>
              </div>
              <h3 className="text-xl font-bold text-white">iTransformer</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Inverts the classical Transformer by projecting individual time series independently into tokens. Excels at modeling dependencies across multivariate series for 1-Week and 1-Month horizons.
              </p>
              <div className="space-y-2 pt-2">
                <div className="flex justify-between text-xs border-b border-white/[0.04] pb-1.5">
                  <span className="text-slate-500">Regression Accuracy (R²)</span>
                  <span className="text-emerald-400 font-mono font-bold">0.8320</span>
                </div>
                <div className="flex justify-between text-xs border-b border-white/[0.04] pb-1.5">
                  <span className="text-slate-500">Lookback Sequence</span>
                  <span className="text-slate-300 font-mono">512 - 1440h</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Embedding Token</span>
                  <span className="text-slate-300 font-mono">Temporal Embeds</span>
                </div>
              </div>
            </div>
          </ScrollReveal>

          {/* Advanced PatchTST */}
          <ScrollReveal className="glass-card border-white/[0.06] p-8 flex flex-col justify-between" style={{ animationDelay: '150ms' }}>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Badge className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono text-[10px]">
                  Subseries Patching
                </Badge>
                <span className="text-slate-500 text-xs font-semibold">v1.0.0</span>
              </div>
              <h3 className="text-xl font-bold text-white">Advanced PatchTST</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Groups local time steps into patches and processes them with vanilla Transformer encoders. Enhanced with calendar embeds to maintain temporal order over extended horizons.
              </p>
              <div className="space-y-2 pt-2">
                <div className="flex justify-between text-xs border-b border-white/[0.04] pb-1.5">
                  <span className="text-slate-500">Regression Accuracy (R²)</span>
                  <span className="text-emerald-400 font-mono font-bold">0.8250</span>
                </div>
                <div className="flex justify-between text-xs border-b border-white/[0.04] pb-1.5">
                  <span className="text-slate-500">Lookback Sequence</span>
                  <span className="text-slate-300 font-mono">512 - 1440h</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Patch Length</span>
                  <span className="text-slate-300 font-mono">16 (Stride 8)</span>
                </div>
              </div>
            </div>
          </ScrollReveal>

          {/* SOTA Hybrid */}
          <ScrollReveal className="glass-card border-white/[0.06] p-8 flex flex-col justify-between" style={{ animationDelay: '300ms' }}>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Badge className="bg-purple-500/10 text-purple-400 border border-purple-500/20 font-mono text-[10px]">
                  Recurrent-Attention
                </Badge>
                <span className="text-slate-500 text-xs font-semibold">v1.0.0</span>
              </div>
              <h3 className="text-xl font-bold text-white">SOTA Hybrid</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Integrates multi-scale patching, BiGRU recurrent layers, and cross-variable attention. Ideal for capturing immediate spatial peaks and daily load shape variations.
              </p>
              <div className="space-y-2 pt-2">
                <div className="flex justify-between text-xs border-b border-white/[0.04] pb-1.5">
                  <span className="text-slate-500">Regression Accuracy (R²)</span>
                  <span className="text-emerald-400 font-mono font-bold">0.8407</span>
                </div>
                <div className="flex justify-between text-xs border-b border-white/[0.04] pb-1.5">
                  <span className="text-slate-500">Lookback Sequence</span>
                  <span className="text-slate-300 font-mono">96 Hours</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Attention Heads</span>
                  <span className="text-slate-300 font-mono">8 Heads</span>
                </div>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* Bottom CTA Section */}
      <section className="relative z-10 py-24 border-t border-white/[0.04] bg-[#0d1321]/20">
        <ScrollReveal className="max-w-4xl mx-auto text-center px-6 space-y-8">
          <h2 className="text-3xl sm:text-5xl font-black text-white leading-tight">
            Connect Your Grid To The Future
          </h2>
          <p className="text-slate-400 text-sm sm:text-base max-w-2xl mx-auto leading-relaxed">
            Register your virtual Linky simulator feed today. Access smart recommendations, automated alerts, and detailed PyTorch deep forecasting.
          </p>
          <div className="pt-4 flex justify-center">
            <Link href="/login">
              <Button className="h-12 px-8 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all duration-300 hover:scale-[1.02] cursor-pointer rounded-xl text-sm flex items-center gap-2">
                Connect Smart Meter
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>
        </ScrollReveal>
      </section>

      {/* Footer */}
      <footer className="relative z-10 max-w-7xl mx-auto w-full px-6 h-20 flex flex-col sm:flex-row items-center justify-between border-t border-white/[0.04] text-xs text-slate-500 gap-4 py-6">
        <p>© 2026 EnergyAI. Master&apos;s PFE Residential Grid Automation Platform.</p>
        <div className="flex gap-6">
          <p>Built with Next.js & PyTorch</p>
          <p>Enedis Linky API Sync</p>
        </div>
      </footer>
    </div>
  );
}
