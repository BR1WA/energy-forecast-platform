"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Zap, Settings, ArrowRight, Loader2, Database, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { authApi, getAccessToken, billingApi, settingsApi } from "@/lib/api";

export default function SetupWizard() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form State
  const [sensorType, setSensorType] = useState("simulator");
  const [sensorApiUrl, setSensorApiUrl] = useState("");
  const [plan, setPlan] = useState("free");

  const handleComplete = async () => {
    setIsSubmitting(true);
    try {
      const payload = {
        country: "Morocco",
        region: "Casablanca-Settat",
        electricity_provider: "ONEE",
        currency: "MAD",
        // Default Moroccan national prices (Tranche 4 as peak, Tranche 1 as off-peak)
        peak_rate: 1.16,
        off_peak_rate: 0.90,
        peak_start_hour: 18,
        peak_end_hour: 22,
        sensor_type: sensorType,
        sensor_api_url: sensorType === "real_api" ? sensorApiUrl : null
      };

      await settingsApi.postSetup(payload);

      // Save user's selected subscription plan
      try {
        if (plan === "free") {
          await billingApi.cancelSubscription();
        } else {
          const checkoutRes = await billingApi.checkout(plan as 'pro' | 'enterprise');
          await billingApi.confirmCheckout(checkoutRes.checkout_ref);
        }
        await refreshUser();
      } catch (authErr) {
        console.error("Failed to update subscription tier during setup:", authErr);
      }
      
      toast.success("Setup complete! Redirecting...");
      setTimeout(() => router.push("/dashboard"), 1500);
    } catch (err) {
      toast.error("Failed to save setup. Please try again.");
      console.error(err);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0F1C] text-slate-200 flex flex-col items-center justify-center p-4">
      {/* Background Glow */}
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-blue-500/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-2xl bg-[#111827]/80 backdrop-blur-xl border border-blue-500/20 rounded-3xl overflow-hidden shadow-2xl relative z-10 animate-in zoom-in-95 duration-300">
        <div className="flex border-b border-white/5 bg-white/[0.02]">
          {[1, 2].map((s) => (
            <div 
              key={s} 
              className={`flex-1 p-5 text-center text-xs font-bold uppercase tracking-wider transition-colors ${
                step === s ? "text-blue-400 border-b-2 border-blue-500 bg-blue-500/5" : "text-slate-500"
              }`}
            >
              {s === 1 ? "Step 1: Telemetry Setup" : "Step 2: Plan Setup"}
            </div>
          ))}
        </div>

        <div className="p-8">
          {step === 1 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500 space-y-6">
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 bg-blue-500/20 text-blue-400 rounded-2xl">
                  <Database className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">Telemetry Integration</h2>
                  <p className="text-slate-400 text-sm">Connect to your Moroccan smart meter or use our simulated stream.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div 
                  onClick={() => setSensorType("simulator")}
                  className={`p-6 rounded-2xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                    sensorType === "simulator" ? "border-blue-500 bg-blue-500/10" : "border-white/10 bg-[#1A2333]/50 hover:border-white/20"
                  }`}
                >
                  <div>
                    <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center mb-4">
                      <Zap className="w-6 h-6 text-blue-400" />
                    </div>
                    <h3 className="text-lg font-bold text-white mb-2">Smart Simulator</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Generates realistic residential electricity telemetry based on Moroccan tiered ONEE usage patterns.
                    </p>
                  </div>
                </div>

                <div 
                  onClick={() => setSensorType("real_api")}
                  className={`p-6 rounded-2xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                    sensorType === "real_api" ? "border-emerald-500 bg-emerald-500/10" : "border-white/10 bg-[#1A2333]/50 hover:border-white/20"
                  }`}
                >
                  <div>
                    <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mb-4">
                      <Settings className="w-6 h-6 text-emerald-400" />
                    </div>
                    <h3 className="text-lg font-bold text-white mb-2">Real IoT Gateway</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Connect directly to an external API endpoint to stream live smart meter JSON telemetry frames.
                    </p>
                  </div>
                </div>
              </div>

              {sensorType === "real_api" && (
                <div className="animate-in fade-in slide-in-from-top-4 mt-6">
                  <label className="block text-xs text-slate-400 font-bold uppercase tracking-wider mb-2">Gateway API Endpoint</label>
                  <input 
                    type="url" 
                    placeholder="https://api.example.com/telemetry"
                    value={sensorApiUrl} 
                    onChange={(e) => setSensorApiUrl(e.target.value)}
                    className="w-full bg-[#1A2333] border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-xl px-4 py-3 text-xs text-white placeholder-slate-600 outline-none transition-all"
                  />
                  <p className="text-[10px] text-slate-500 mt-2 leading-relaxed">
                    Must return an array of 96 historical hourly readings containing [GAP, GRP, V, GI, SM1, SM2, SM3].
                  </p>
                </div>
              )}

              <div className="flex justify-end pt-6">
                <button 
                  onClick={() => setStep(2)}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-bold text-xs transition-all shadow-lg shadow-blue-500/20"
                >
                  Next: Choose Plan <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500 space-y-6">
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 bg-amber-500/20 text-amber-400 rounded-2xl">
                  <Sparkles className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">Choose Your Plan</h2>
                  <p className="text-slate-400 text-sm">Select a subscription tier to launch the energy platform.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { id: "free", name: "Free", price: "0", desc: "Basic forecasting & live telemetry." },
                  { id: "pro", name: "Pro", price: "99", desc: "SOTA AI models & shifting advice." },
                  { id: "enterprise", name: "Enterprise", price: "499", desc: "Custom fine-tuning & multi-site grids." }
                ].map((p) => (
                  <div
                    key={p.id}
                    onClick={() => setPlan(p.id)}
                    className={`p-5 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between h-40 ${
                      plan === p.id 
                        ? p.id === "pro" 
                          ? "border-amber-500 bg-amber-500/5 shadow-[0_0_15px_rgba(245,158,11,0.1)]" 
                          : p.id === "enterprise"
                          ? "border-purple-500 bg-purple-500/5 shadow-[0_0_15px_rgba(168,85,247,0.1)]"
                          : "border-blue-500 bg-blue-500/5 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
                        : "border-white/10 bg-[#1A2333]/50 hover:border-white/20"
                    }`}
                  >
                    <div>
                      <h3 className="font-bold text-white text-sm">{p.name}</h3>
                      <p className="text-[10px] text-slate-400 mt-1.5 leading-normal">{p.desc}</p>
                    </div>
                    <div>
                      <p className="text-lg font-black text-white font-mono">{p.price} <span className="text-[10px] text-slate-400 font-normal">MAD/mo</span></p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-between pt-8 border-t border-white/5">
                <button 
                  onClick={() => setStep(1)}
                  className="px-6 py-3 rounded-xl font-bold text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Back
                </button>
                <button 
                  onClick={handleComplete}
                  disabled={isSubmitting}
                  className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-8 py-3 rounded-xl font-bold text-xs transition-all shadow-[0_0_20px_rgba(16,185,129,0.2)] hover:shadow-[0_0_30px_rgba(16,185,129,0.4)] disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Finalizing...</>
                  ) : (
                    <>Complete Setup <Zap className="w-4 h-4 fill-current" /></>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
