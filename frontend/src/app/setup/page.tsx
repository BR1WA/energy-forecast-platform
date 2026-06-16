"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Globe, Zap, Settings, ArrowRight, Loader2, Database, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { authApi, getAccessToken } from "@/lib/api";

const providerTariffs: Record<string, {
  peakRate: number;
  offPeakRate: number;
  peakStartHour: number;
  peakEndHour: number;
}> = {
  "Lydec": { peakRate: 1.50, offPeakRate: 0.85, peakStartHour: 18, peakEndHour: 23 },
  "Redal": { peakRate: 1.52, offPeakRate: 0.88, peakStartHour: 18, peakEndHour: 23 },
  "Amendis": { peakRate: 1.55, offPeakRate: 0.90, peakStartHour: 18, peakEndHour: 23 },
  "RADEEMA": { peakRate: 1.48, offPeakRate: 0.82, peakStartHour: 18, peakEndHour: 23 },
  "RAMSA": { peakRate: 1.46, offPeakRate: 0.81, peakStartHour: 18, peakEndHour: 23 },
  "RADEEF": { peakRate: 1.50, offPeakRate: 0.83, peakStartHour: 18, peakEndHour: 23 },
  "RADEEJ": { peakRate: 1.45, offPeakRate: 0.80, peakStartHour: 18, peakEndHour: 23 },
  "RADEECO": { peakRate: 1.42, offPeakRate: 0.79, peakStartHour: 18, peakEndHour: 23 },
  "ONEE": { peakRate: 1.45, offPeakRate: 0.80, peakStartHour: 18, peakEndHour: 23 }
};

export default function SetupWizard() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form State
  const [country] = useState("Morocco");
  const [region, setRegion] = useState("Casablanca-Settat");
  const [provider, setProvider] = useState("Lydec");
  const [currency] = useState("MAD");
  
  const [peakRate, setPeakRate] = useState("1.50");
  const [offPeakRate, setOffPeakRate] = useState("0.85");
  const [peakStart, setPeakStart] = useState("18");
  const [peakEnd, setPeakEnd] = useState("23");

  const [sensorType, setSensorType] = useState("simulator");
  const [sensorApiUrl, setSensorApiUrl] = useState("");
  const [plan, setPlan] = useState("free");

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    const tariff = providerTariffs[newProvider];
    if (tariff) {
      setPeakRate(tariff.peakRate.toFixed(2));
      setOffPeakRate(tariff.offPeakRate.toFixed(2));
      setPeakStart(String(tariff.peakStartHour));
      setPeakEnd(String(tariff.peakEndHour));
    }
  };

  const handleRegionChange = (newRegion: string) => {
    setRegion(newRegion);
    let defaultProvider = "ONEE";
    if (newRegion === "Casablanca-Settat") defaultProvider = "Lydec";
    else if (newRegion === "Rabat-Salé-Kénitra") defaultProvider = "Redal";
    else if (newRegion === "Tanger-Tétouan-Al Hoceïma") defaultProvider = "Amendis";
    else if (newRegion === "Marrakech-Safi") defaultProvider = "RADEEMA";
    else if (newRegion === "Souss-Massa") defaultProvider = "RAMSA";
    else if (newRegion === "Fès-Meknès") defaultProvider = "RADEEF";
    else if (newRegion === "L'Oriental") defaultProvider = "RADEECO";
    
    handleProviderChange(defaultProvider);
  };

  const handleComplete = async () => {
    setIsSubmitting(true);
    try {
      const payload = {
        country,
        region,
        electricity_provider: provider,
        currency,
        peak_rate: parseFloat(peakRate),
        off_peak_rate: parseFloat(offPeakRate),
        peak_start_hour: parseInt(peakStart),
        peak_end_hour: parseInt(peakEnd),
        sensor_type: sensorType,
        sensor_api_url: sensorType === "real_api" ? sensorApiUrl : null
      };

      const token = getAccessToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("http://localhost:8000/api/v1/settings/setup", {
        method: "POST",
        headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Failed to save setup settings");

      // Save user's selected subscription plan
      try {
        await authApi.updateProfile({ subscription_tier: plan });
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

      <div className="w-full max-w-2xl bg-[#111827]/80 backdrop-blur-xl border border-blue-500/20 rounded-3xl overflow-hidden shadow-2xl relative z-10">
        <div className="flex border-b border-white/5">
          {[1, 2, 3, 4].map((s) => (
            <div key={s} className={`flex-1 p-4 text-center text-sm font-medium transition-colors ${step === s ? "text-blue-400 border-b-2 border-blue-500" : "text-slate-500"}`}>
              Step {s}
            </div>
          ))}
        </div>

        <div className="p-8">
          {step === 1 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500 space-y-6">
              <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-blue-500/20 text-blue-400 rounded-2xl">
                  <Globe className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">Localization</h2>
                  <p className="text-slate-400">Configure your region and energy provider.</p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Country</label>
                  <input 
                    type="text" 
                    value="Morocco" 
                    disabled 
                    className="w-full bg-[#1A2333]/50 border border-white/10 rounded-xl px-4 py-3 text-slate-400 cursor-not-allowed outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Region</label>
                  <select 
                    value={region} 
                    onChange={(e) => handleRegionChange(e.target.value)}
                    className="w-full bg-[#1A2333] border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-colors"
                  >
                    <option value="Tanger-Tétouan-Al Hoceïma">Tanger-Tétouan-Al Hoceïma</option>
                    <option value="L'Oriental">L&apos;Oriental</option>
                    <option value="Fès-Meknès">Fès-Meknès</option>
                    <option value="Rabat-Salé-Kénitra">Rabat-Salé-Kénitra</option>
                    <option value="Béni Mellal-Khénifra">Béni Mellal-Khénifra</option>
                    <option value="Casablanca-Settat">Casablanca-Settat</option>
                    <option value="Marrakech-Safi">Marrakech-Safi</option>
                    <option value="Drâa-Tafilalet">Drâa-Tafilalet</option>
                    <option value="Souss-Massa">Souss-Massa</option>
                    <option value="Guelmim-Oued Noun">Guelmim-Oued Noun</option>
                    <option value="Laâyoune-Sakia El Hamra">Laâyoune-Sakia El Hamra</option>
                    <option value="Dakhla-Oued Ed-Dahab">Dakhla-Oued Ed-Dahab</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Electricity Provider</label>
                    <select 
                      value={provider} 
                      onChange={(e) => handleProviderChange(e.target.value)}
                      className="w-full bg-[#1A2333] border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-colors"
                    >
                      <option value="Lydec">Lydec (Casablanca)</option>
                      <option value="Redal">Redal (Rabat-Salé)</option>
                      <option value="Amendis">Amendis (Tanger-Tétouan)</option>
                      <option value="RADEEMA">RADEEMA (Marrakech)</option>
                      <option value="RAMSA">RAMSA (Agadir)</option>
                      <option value="RADEEF">RADEEF (Fès)</option>
                      <option value="RADEEJ">RADEEJ (El Jadida)</option>
                      <option value="RADEECO">RADEECO (Oujda)</option>
                      <option value="ONEE">ONEE (National Office)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Currency</label>
                    <input 
                      type="text" 
                      value="MAD" 
                      disabled 
                      className="w-full bg-[#1A2333]/50 border border-white/10 rounded-xl px-4 py-3 text-slate-400 cursor-not-allowed outline-none font-mono"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-6">
                <button 
                  onClick={() => setStep(2)}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium transition-all"
                >
                  Next Step <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500 space-y-6">
              <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-purple-500/20 text-purple-400 rounded-2xl">
                  <Zap className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">Tariff Configuration</h2>
                  <p className="text-slate-400">Set your pricing to accurately calculate costs.</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-sm font-medium text-purple-400 uppercase tracking-wider">Peak Hours</h3>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Time Range (24h)</label>
                    <div className="flex items-center gap-2">
                      <input 
                        type="number" min="0" max="23" value={peakStart} onChange={(e) => setPeakStart(e.target.value)}
                        className="w-full bg-[#1A2333] border border-white/10 rounded-xl px-3 py-2 text-center text-white"
                      />
                      <span className="text-slate-500">to</span>
                      <input 
                        type="number" min="0" max="23" value={peakEnd} onChange={(e) => setPeakEnd(e.target.value)}
                        className="w-full bg-[#1A2333] border border-white/10 rounded-xl px-3 py-2 text-center text-white"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Rate ({currency} / kWh)</label>
                    <input 
                      type="number" step="0.01" value={peakRate} onChange={(e) => setPeakRate(e.target.value)}
                      className="w-full bg-[#1A2333] border border-white/10 rounded-xl px-4 py-3 text-white"
                    />
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="text-sm font-medium text-emerald-400 uppercase tracking-wider">Off-Peak Hours</h3>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Time Range (24h)</label>
                    <div className="flex items-center gap-2 h-[42px] px-3 bg-white/5 rounded-xl border border-white/5 text-slate-400 text-sm">
                      Remaining hours of the day
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Rate ({currency} / kWh)</label>
                    <input 
                      type="number" step="0.01" value={offPeakRate} onChange={(e) => setOffPeakRate(e.target.value)}
                      className="w-full bg-[#1A2333] border border-white/10 rounded-xl px-4 py-3 text-white"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-between pt-6">
                <button 
                  onClick={() => setStep(1)}
                  className="px-6 py-3 rounded-xl font-medium text-slate-400 hover:text-white transition-colors"
                >
                  Back
                </button>
                <button 
                  onClick={() => setStep(3)}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-medium transition-all"
                >
                  Next Step <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500 space-y-6">
              <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-emerald-500/20 text-emerald-400 rounded-2xl">
                  <Database className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">Sensor Integration</h2>
                  <p className="text-slate-400">Connect to your smart meter or use our simulator.</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div 
                  onClick={() => setSensorType("simulator")}
                  className={`p-6 rounded-2xl border-2 cursor-pointer transition-all ${sensorType === "simulator" ? "border-blue-500 bg-blue-500/10" : "border-white/10 bg-[#1A2333] hover:border-white/20"}`}
                >
                  <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center mb-4">
                    <Zap className="w-6 h-6 text-blue-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Simulator</h3>
                  <p className="text-sm text-slate-400">Generates highly realistic synthetic telemetry based on {country} consumption patterns.</p>
                </div>

                <div 
                  onClick={() => setSensorType("real_api")}
                  className={`p-6 rounded-2xl border-2 cursor-pointer transition-all ${sensorType === "real_api" ? "border-emerald-500 bg-emerald-500/10" : "border-white/10 bg-[#1A2333] hover:border-white/20"}`}
                >
                  <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mb-4">
                    <Settings className="w-6 h-6 text-emerald-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Real IoT Gateway</h3>
                  <p className="text-sm text-slate-400">Connect directly to an external API to fetch live JSON telemetry frames.</p>
                </div>
              </div>

              {sensorType === "real_api" && (
                <div className="animate-in fade-in slide-in-from-top-4 mt-6">
                  <label className="block text-sm font-medium text-slate-400 mb-2">Gateway API Endpoint</label>
                  <input 
                    type="url" 
                    placeholder="https://api.example.com/telemetry"
                    value={sensorApiUrl} 
                    onChange={(e) => setSensorApiUrl(e.target.value)}
                    className="w-full bg-[#1A2333] border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors"
                  />
                  <p className="text-xs text-slate-500 mt-2">
                    Must return an array of 96 historical hourly readings containing [GAP, GRP, V, GI, SM1, SM2, SM3].
                  </p>
                </div>
              )}

              <div className="flex justify-between pt-6">
                <button 
                  onClick={() => setStep(2)}
                  className="px-6 py-3 rounded-xl font-medium text-slate-400 hover:text-white transition-colors"
                >
                  Back
                </button>
                <button 
                  onClick={() => setStep(4)}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-xl font-medium transition-all"
                >
                  Next Step <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-500 space-y-6">
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 bg-amber-500/20 text-amber-400 rounded-2xl">
                  <Sparkles className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">Choose Your Plan</h2>
                  <p className="text-slate-400">Select a subscription tier to launch the platform.</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {[
                  { id: "free", name: "Free", price: "0", desc: "Basic forecasting & telemetry." },
                  { id: "pro", name: "Pro", price: "99", desc: "SOTA AI & load optimization." },
                  { id: "enterprise", name: "Enterprise", price: "499", desc: "Custom fine-tuning & support." }
                ].map((p) => (
                  <div
                    key={p.id}
                    onClick={() => setPlan(p.id)}
                    className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between h-40 ${
                      plan === p.id 
                        ? p.id === "pro" 
                          ? "border-amber-500 bg-amber-500/5 shadow-[0_0_15px_rgba(245,158,11,0.1)]" 
                          : p.id === "enterprise"
                          ? "border-purple-500 bg-purple-500/5 shadow-[0_0_15px_rgba(168,85,247,0.1)]"
                          : "border-blue-500 bg-blue-500/5 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
                        : "border-white/10 bg-[#1A2333] hover:border-white/20"
                    }`}
                  >
                    <div>
                      <h3 className="font-bold text-white text-sm">{p.name}</h3>
                      <p className="text-[10px] text-slate-400 mt-1 leading-normal">{p.desc}</p>
                    </div>
                    <div>
                      <p className="text-lg font-black text-white font-mono">{p.price} <span className="text-[10px] text-slate-400 font-normal">MAD/mo</span></p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-between pt-6">
                <button 
                  onClick={() => setStep(3)}
                  className="px-6 py-3 rounded-xl font-medium text-slate-400 hover:text-white transition-colors"
                >
                  Back
                </button>
                <button 
                  onClick={handleComplete}
                  disabled={isSubmitting}
                  className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-8 py-3 rounded-xl font-medium transition-all shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <><Loader2 className="w-5 h-5 animate-spin" /> Finalizing...</>
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
