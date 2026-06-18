"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AppLayout from "@/components/layout/app-layout";
import { useAuth } from "@/lib/auth";
import { authApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, Sparkles, Zap, Building, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function PlansPage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

  const handleSelectPlan = async (tier: string) => {
    const isCurrent = currentTier === tier;
    const targetTier = isCurrent ? "free" : tier;
    setSelectedPlan(tier);
    try {
      await authApi.changeSubscription(targetTier);
      await refreshUser();
      if (isCurrent) {
        toast.success("Subscription cancelled. Downgraded to Free tier.");
      } else {
        toast.success(`Plan updated successfully to ${tier.toUpperCase()}!`);
      }
      setTimeout(() => {
        router.push("/dashboard");
      }, 1000);
    } catch (err) {
      toast.error("Failed to update subscription plan. Please try again.");
      console.error(err);
    } finally {
      setSelectedPlan(null);
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
        "Smart load-shifting notifications & suggestions",
        "Priority email support",
      ],
    },
    {
      id: "enterprise",
      name: "Enterprise",
      price: "499",
      description: "Tailored solutions for businesses and multi-site grids.",
      icon: Building,
      iconColor: "text-purple-400 bg-purple-500/10 border-purple-500/20",
      accent: "border-purple-500/30 bg-[#111827]/50",
      buttonText: "Go Enterprise",
      features: [
        "Everything in Pro Plan",
        "Custom ML model fine-tuning per site pattern",
        "Unlimited smart meter integrations & aggregations",
        "Direct SMTP custom email alerts & warnings",
        "API Gateway access for raw JSON telemetry export",
        "24/7 Dedicated Account Manager & grid auditor",
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
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
                        : plan.id === "enterprise"
                        ? "bg-purple-600 hover:bg-purple-500 text-white shadow-[0_0_20px_rgba(168,85,247,0.2)] hover:shadow-[0_0_25px_rgba(168,85,247,0.3)]"
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
                        const tierRanks: Record<string, number> = { free: 0, pro: 1, enterprise: 2 };
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
    </AppLayout>
  );
}
