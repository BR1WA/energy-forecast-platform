"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AppLayout from "@/components/layout/app-layout";
import { useAuth } from "@/lib/auth";
import { authApi, billingApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, Sparkles, Zap, Building, Loader2, CreditCard, Lock, ShieldCheck, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function PlansPage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

  // Checkout Modal State
  const [checkoutPlan, setCheckoutPlan] = useState<any | null>(null);
  const [checkoutStep, setCheckoutStep] = useState<'details' | 'processing' | 'confirming' | 'success'>('details');
  const [checkoutRef, setCheckoutRef] = useState<string>('');
  const [cardHolder, setCardHolder] = useState(user?.full_name || '');
  const [cardNumber, setCardNumber] = useState('');
  const [cardExpiry, setCardExpiry] = useState('');
  const [cardCvv, setCardCvv] = useState('');
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  // Cancel/Downgrade Modal State
  const [showCancelModal, setShowCancelModal] = useState(false);

  const handleSelectPlan = async (tier: string) => {
    const isCurrent = currentTier === tier;
    if (isCurrent && tier === "pro") {
      setShowCancelModal(true);
    } else if (tier === "free" && currentTier !== "free") {
      setShowCancelModal(true);
    } else if (!isCurrent && tier === "pro") {
      // Find the plan object
      const targetPlan = plans.find(p => p.id === tier);
      if (targetPlan) {
        setCheckoutPlan(targetPlan);
        setCheckoutStep('details');
        setCheckoutError(null);
        setCardNumber('');
        setCardExpiry('');
        setCardCvv('');
        setCardHolder(user?.full_name || '');
      }
    }
  };

  const confirmCancellation = async () => {
    setShowCancelModal(false);
    setSelectedPlan("free");
    try {
      await billingApi.cancelSubscription();
      toast.success("Subscription cancelled. Downgraded to Free tier.");
      await refreshUser();
      setTimeout(() => {
        router.push("/dashboard");
      }, 1000);
    } catch (err) {
      toast.error("Failed to cancel subscription. Please try again.");
      console.error(err);
    } finally {
      setSelectedPlan(null);
    }
  };

  const handleCardNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '');
    const formatted = value.match(/.{1,4}/g)?.join(' ') || '';
    setCardNumber(formatted.substring(0, 19));
  };

  const handleExpiryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '');
    let formatted = value;
    if (value.length > 2) {
      formatted = `${value.substring(0, 2)}/${value.substring(2, 4)}`;
    }
    setCardExpiry(formatted.substring(0, 5));
  };

  const handleCvvChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '');
    setCardCvv(value.substring(0, 3));
  };

  const handleCheckoutSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cardHolder || cardNumber.length < 19 || cardExpiry.length < 5 || cardCvv.length < 3) {
      setCheckoutError("Please fill in valid payment details.");
      return;
    }
    setCheckoutError(null);
    setCheckoutStep('processing');

    try {
      // Step 1: Create checkout intent
      const checkoutRes = await billingApi.checkout(checkoutPlan.id as 'pro');
      setCheckoutRef(checkoutRes.checkout_ref);

      // Transition to confirming state (webhook simulation)
      setCheckoutStep('confirming');

      // Add a small delay to simulate asynchronous webhook delivery
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Step 2: Confirm checkout
      await billingApi.confirmCheckout(checkoutRes.checkout_ref);
      await refreshUser();
      
      setCheckoutStep('success');
    } catch (err: any) {
      setCheckoutError(err.message || "Payment processing failed. Please try again.");
      setCheckoutStep('details');
    }
  };

  const plans = [
    {
      id: "free",
      name: "Free Plan",
      price: "0",
      description: "Ideal for basic household monitoring.",
      icon: Zap,
      iconColor: "text-slate-400 bg-slate-500/10 border-slate-500/20",
      accent: "border-white/5 bg-[#111827]/50",
      buttonText: "Switch to Free",
      features: [
        "Basic CNN-BiLSTM & PatchTST Models",
        "1-Hour standard lookback window",
        "Single smart meter configuration",
        "Standard community support",
      ],
    },
    {
      id: "pro",
      name: "Pro Plan",
      price: "99",
      description: "Advanced forecasting and load optimization advice.",
      icon: Sparkles,
      iconColor: "text-amber-400 bg-amber-500/10 border-amber-500/20",
      accent: "border-amber-500/30 bg-[#111827]/80 ring-2 ring-amber-500/10",
      popular: true,
      buttonText: "Upgrade to Pro",
      features: [
        "Everything in Free Plan",
        "SOTA Hybrid AI Forecasting model access",
        "Real-time Linky WebSocket telemetry stream",
        "Dynamic peak/off-peak cost analysis",
        "Full analytics suite & Heatmap visualization",
        "Multi-site grid management",
        "PDF export & advanced reports",
        "Smart load-shifting notifications & suggestions",
        "Priority email support",
      ],
    },
  ];

  const currentTier = user?.subscription_tier || "free";

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-8 py-4">
        {/* Header Section */}
        <div className="text-center space-y-3">
          <h1 className="text-3xl font-extrabold text-white tracking-tight bg-gradient-to-r from-blue-400 via-cyan-400 to-emerald-400 bg-clip-text text-transparent">
            Choose Your Subscription Plan
          </h1>
          <p className="text-slate-400 text-sm max-w-xl mx-auto">
            Upgrade to unlock premium machine learning forecasting models, load-shifting tips, and real-time smart meter telemetry integrations.
          </p>
        </div>

        {/* Plans Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 max-w-3xl mx-auto">
          {plans.map((plan) => {
            const Icon = plan.icon;
            const isCurrent = currentTier === plan.id;
            const isLoading = selectedPlan === plan.id;

            return (
              <Card
                key={plan.id}
                className={`relative flex flex-col justify-between border backdrop-blur-xl transition-all duration-300 rounded-3xl overflow-hidden hover:-translate-y-1 hover:shadow-2xl hover:shadow-black/50 ${plan.accent} ${
                  isCurrent ? "shadow-2xl shadow-blue-500/5 ring-1 ring-blue-500/25" : ""
                }`}
              >
                {/* Popular Badge */}
                {plan.popular && (
                  <div className="absolute top-0 right-6 -translate-y-1/2">
                    <span className="bg-gradient-to-r from-amber-500 to-orange-500 text-white font-extrabold text-[10px] uppercase px-3 py-1 rounded-full shadow-[0_0_20px_rgba(245,158,11,0.3)]">
                      Popular
                    </span>
                  </div>
                )}

                {/* Card Header & Price */}
                <CardHeader className="pb-4">
                  <div className="flex items-center justify-between mb-4">
                    <div className={`p-2.5 rounded-2xl border ${plan.iconColor}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    {isCurrent && (
                      <span className="bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] font-bold uppercase px-2.5 py-1 rounded-full">
                        Current Plan
                      </span>
                    )}
                  </div>

                  <CardTitle className="text-xl font-bold text-white">
                    {plan.name}
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-400 min-h-[32px] mt-1">
                    {plan.description}
                  </CardDescription>

                  <div className="mt-6 flex items-baseline gap-1.5">
                    <span className="text-3xl font-black text-white font-mono">
                      {plan.price}
                    </span>
                    <span className="text-slate-400 font-medium text-xs font-mono">MAD</span>
                    <span className="text-slate-500 text-xs">/month</span>
                  </div>
                </CardHeader>

                {/* Features List */}
                <CardContent className="space-y-6 flex-1 flex flex-col justify-between">
                  <ul className="space-y-3.5 pt-2">
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-300">
                        <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    onClick={() => handleSelectPlan(plan.id)}
                    disabled={(isCurrent && plan.id === "free") || selectedPlan !== null}
                    className={`w-full mt-8 py-5 font-bold text-xs rounded-xl transition-all duration-200 ${
                      isCurrent
                        ? plan.id === "free"
                          ? "bg-slate-800 text-slate-500 cursor-not-allowed hover:bg-slate-800 border-white/5"
                          : "bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 border border-red-500/30 hover:border-red-500/50"
                        : plan.id === "pro"
                        ? "bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white shadow-[0_0_20px_rgba(245,158,11,0.2)] hover:shadow-[0_0_25px_rgba(245,158,11,0.3)]"
                        : "bg-white/5 hover:bg-white/10 text-white border border-white/10 hover:border-white/20"
                    }`}
                  >
                    {isLoading ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" /> Processing...
                      </span>
                    ) : isCurrent ? (
                      plan.id === "free" ? "Active Free Tier" : "Cancel Subscription"
                    ) : (
                      (() => {
                        const tierRanks: Record<string, number> = { free: 0, pro: 1 };
                        const currentRank = tierRanks[currentTier] ?? 0;
                        const targetRank = tierRanks[plan.id] ?? 0;
                        return targetRank > currentRank ? plan.buttonText : `Downgrade to ${plan.name.replace(" Plan", "")}`;
                      })()
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Checkout Modal */}
      {checkoutPlan && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-in fade-in duration-300">
          <div className="relative w-full max-w-md bg-[#0b0f19] border border-white/[0.08] rounded-3xl overflow-hidden shadow-2xl shadow-black/85 flex flex-col animate-in zoom-in-95 duration-200">
            
            {/* Close Button */}
            {checkoutStep !== 'processing' && checkoutStep !== 'confirming' && checkoutStep !== 'success' && (
              <button
                onClick={() => setCheckoutPlan(null)}
                className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 hover:bg-white/5 rounded-full transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}

            {/* Progress Stepper */}
            <div className="px-6 pt-6 pb-2 border-b border-white/[0.04]">
              <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
                <span>Checkout Progress</span>
                <span>
                  {checkoutStep === 'details' && 'Step 1 of 3'}
                  {(checkoutStep === 'processing' || checkoutStep === 'confirming') && 'Step 2 of 3'}
                  {checkoutStep === 'success' && 'Step 3 of 3'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className={`h-1.5 rounded-full ${checkoutStep === 'details' ? 'bg-blue-500' : 'bg-emerald-500'}`} />
                <div className={`h-1.5 rounded-full ${
                  checkoutStep === 'details' ? 'bg-white/5' :
                  checkoutStep === 'processing' ? 'bg-blue-500/50 animate-pulse' :
                  checkoutStep === 'confirming' ? 'bg-blue-500' : 'bg-emerald-500'
                }`} />
                <div className={`h-1.5 rounded-full ${checkoutStep === 'success' ? 'bg-emerald-500' : 'bg-white/5'}`} />
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6">
              {checkoutStep === 'details' && (
                <form onSubmit={handleCheckoutSubmit} className="space-y-4">
                  {/* Header info */}
                  <div className="flex justify-between items-center bg-white/[0.02] border border-white/[0.04] p-4 rounded-2xl mb-4">
                    <div>
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Subscription Tier</span>
                      <h4 className="text-sm font-extrabold text-white">{checkoutPlan.name}</h4>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Total price</span>
                      <p className="text-sm font-extrabold text-white font-mono">{checkoutPlan.price} MAD <span className="text-[10px] text-slate-400 font-normal">/mo</span></p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <CreditCard className="w-4 h-4 text-blue-400" /> Payment Details
                    </h3>
                    <span className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider animate-pulse">
                      Simulated Sandbox
                    </span>
                  </div>

                  {/* Inputs */}
                  <div className="space-y-3">
                    <div>
                      <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">Cardholder Name</label>
                      <input
                        type="text"
                        required
                        value={cardHolder}
                        onChange={(e) => setCardHolder(e.target.value)}
                        placeholder="John Doe"
                        className="w-full bg-white/[0.02] border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-600 outline-none transition-all"
                      />
                    </div>

                    <div>
                      <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">Card Number</label>
                      <input
                        type="text"
                        required
                        value={cardNumber}
                        onChange={handleCardNumberChange}
                        placeholder="4000 1234 5678 9010"
                        className="w-full bg-white/[0.02] border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-600 outline-none transition-all font-mono"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">Expiration Date</label>
                        <input
                          type="text"
                          required
                          value={cardExpiry}
                          onChange={handleExpiryChange}
                          placeholder="MM/YY"
                          className="w-full bg-white/[0.02] border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-600 outline-none transition-all font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">CVV</label>
                        <input
                          type="password"
                          required
                          value={cardCvv}
                          onChange={handleCvvChange}
                          placeholder="•••"
                          className="w-full bg-white/[0.02] border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-600 outline-none transition-all font-mono"
                        />
                      </div>
                    </div>
                  </div>

                  {checkoutError && (
                    <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs mt-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{checkoutError}</span>
                    </div>
                  )}

                  {/* Notice block */}
                  <div className="flex gap-2 p-3 rounded-xl bg-amber-500/5 border border-amber-500/10 text-amber-400 text-[10px] leading-relaxed mt-4">
                    <Lock className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>This is a simulated sandbox checkout. No actual charges will be processed, but an auditable subscription record will be registered in the backend.</span>
                  </div>

                  <Button
                    type="submit"
                    className="w-full bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-bold py-3 mt-4 text-xs rounded-xl shadow-lg shadow-blue-500/20"
                  >
                    Process Payment (MAD {checkoutPlan.price})
                  </Button>
                </form>
              )}

              {/* Processing States */}
              {(checkoutStep === 'processing' || checkoutStep === 'confirming') && (
                <div className="py-12 flex flex-col items-center justify-center text-center space-y-6">
                  <div className="relative w-16 h-16 flex items-center justify-center">
                    <div className="absolute inset-0 rounded-full border-4 border-white/5" />
                    <div className="absolute inset-0 rounded-full border-4 border-t-blue-500 border-r-blue-500/30 animate-spin" />
                    <Lock className="w-6 h-6 text-blue-400" />
                  </div>
                  
                  <div className="space-y-2 max-w-xs">
                    <h4 className="text-sm font-bold text-white">
                      {checkoutStep === 'processing' ? 'Initializing secure checkout session...' : 'Awaiting payment confirmation webhook...'}
                    </h4>
                    <p className="text-xs text-slate-400">
                      {checkoutStep === 'processing' 
                        ? 'Opening checkout intent & creating database transaction...'
                        : 'Stripe API webhook received. Resolving status changes.'}
                    </p>
                  </div>

                  {/* Simulated Webhook status bar */}
                  <div className="w-full bg-white/5 border border-white/[0.04] p-4 rounded-2xl flex flex-col items-start space-y-2 mt-4">
                    <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
                      <span className={`w-2.5 h-2.5 rounded-full ${checkoutStep === 'confirming' ? 'bg-emerald-500 animate-pulse' : 'bg-blue-500'}`} />
                      <span className="text-white">API Response status</span>
                    </div>
                    <p className="text-[10px] text-slate-400 text-left font-mono">
                      {checkoutStep === 'processing'
                        ? `POST /api/v1/billing/checkout -> 200 OK (pending)`
                        : `POST /api/v1/billing/checkout/confirm -> Processing...`}
                    </p>
                    {checkoutRef && (
                      <p className="text-[9px] text-slate-500 text-left font-mono truncate w-full">
                        Reference: {checkoutRef}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Success State */}
              {checkoutStep === 'success' && (
                <div className="py-10 flex flex-col items-center justify-center text-center space-y-6">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shadow-lg shadow-emerald-500/10 animate-bounce">
                    <ShieldCheck className="w-8 h-8 text-emerald-400" />
                  </div>

                  <div className="space-y-2 max-w-xs">
                    <h4 className="text-lg font-bold text-white">Payment Successful!</h4>
                    <p className="text-xs text-slate-400">
                      Your subscription has been activated successfully. All features in the <span className="text-white font-semibold">{checkoutPlan?.name}</span> are now unlocked.
                    </p>
                  </div>

                  <div className="w-full bg-emerald-500/5 border border-emerald-500/10 p-4 rounded-2xl space-y-1 mt-4">
                    <div className="flex justify-between text-xs text-slate-400">
                      <span>New Tier</span>
                      <span className="text-white font-bold uppercase text-[10px] font-mono tracking-wider">{checkoutPlan?.name}</span>
                    </div>
                    <div className="flex justify-between text-xs text-slate-400">
                      <span>Status</span>
                      <span className="text-emerald-400 font-bold uppercase text-[10px] font-mono tracking-wider">Active</span>
                    </div>
                  </div>

                  <Button
                    onClick={() => {
                      setCheckoutPlan(null);
                      router.push("/dashboard");
                    }}
                    className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 mt-4 text-xs rounded-xl shadow-lg shadow-emerald-500/20"
                  >
                    Proceed to Dashboard
                  </Button>
                </div>
              )}
            </div>

          </div>
        </div>
      )}

      {/* Cancellation Confirmation Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-in fade-in duration-300">
          <div className="relative w-full max-w-sm bg-[#0b0f19] border border-white/[0.08] rounded-3xl overflow-hidden shadow-2xl shadow-black/85 p-6 animate-in zoom-in-95 duration-200">
            <button
              onClick={() => setShowCancelModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 hover:bg-white/5 rounded-full transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <div className="flex flex-col items-center justify-center text-center space-y-4 pt-2">
              <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center shadow-lg shadow-red-500/10">
                <AlertCircle className="w-6 h-6 text-red-400" />
              </div>

              <div className="space-y-2">
                <h3 className="text-lg font-bold text-white">Cancel Subscription?</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Are you sure you want to cancel your premium subscription? You will immediately lose access to premium AI forecasting, WebSocket telemetry, and multi-site grids.
                </p>
              </div>

              <div className="w-full pt-4 flex flex-col gap-2">
                <Button
                  onClick={confirmCancellation}
                  className="w-full bg-red-600 hover:bg-red-500 text-white font-bold py-2.5 text-xs rounded-xl"
                >
                  Yes, Cancel Subscription
                </Button>
                <Button
                  onClick={() => setShowCancelModal(false)}
                  variant="outline"
                  className="w-full bg-white/5 hover:bg-white/10 text-white border border-white/10 hover:border-white/20 font-bold py-2.5 text-xs rounded-xl"
                >
                  No, Keep Premium Access
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}

