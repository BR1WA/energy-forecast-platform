'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/lib/auth';
import { authApi, alertsApi, settingsApi, billingApi, forecastApi } from '@/lib/api';
import { useTheme } from 'next-themes';
import { useI18n, Language } from '@/lib/i18n';
import { toast } from 'sonner';
import { Shield, Bell, Lock, Moon, Sun, Monitor, AlertTriangle, CheckCircle, Globe, CreditCard, AlertCircle, Zap, Cpu, Sparkles } from 'lucide-react';

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useI18n();
  const router = useRouter();

  // Model settings state
  const [modelsList, setModelsList] = useState<any[]>([]);
  const [selectedModel24, setSelectedModel24] = useState('sota');
  const [selectedModel168, setSelectedModel168] = useState('itransformer_168');
  const [selectedModel720, setSelectedModel720] = useState('itransformer_720');
  const [isSavingModels, setIsSavingModels] = useState(false);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const data = await forecastApi.getModels();
        setModelsList(data);
      } catch (err) {
        console.error("Failed to load models for settings page:", err);
      }
    };
    fetchModels();
  }, []);

  useEffect(() => {
    if (user?.preferences) {
      if (user.preferences.default_model_24) setSelectedModel24(user.preferences.default_model_24);
      if (user.preferences.default_model_168) setSelectedModel168(user.preferences.default_model_168);
      if (user.preferences.default_model_720) setSelectedModel720(user.preferences.default_model_720);
    }
  }, [user]);

  const handleSaveModels = async () => {
    setIsSavingModels(true);
    try {
      await settingsApi.updatePreferences({
        default_model_24: selectedModel24,
        default_model_168: selectedModel168,
        default_model_720: selectedModel720,
      });
      await refreshUser();
      toast.success("Default forecasting models updated successfully!");
    } catch (err) {
      console.error("Failed to save default models:", err);
      toast.error("Failed to save model configurations.");
    } finally {
      setIsSavingModels(false);
    }
  };
  const [isCancelling, setIsCancelling] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);

  const handleCancelSubscription = () => {
    setShowCancelModal(true);
  };

  const confirmCancellation = async () => {
    setShowCancelModal(false);
    setIsCancelling(true);
    try {
      await billingApi.cancelSubscription();
      await refreshUser();
      toast.success("Subscription cancelled. Downgraded to Free tier.");
    } catch (err) {
      toast.error("Failed to cancel subscription. Please try again.");
      console.error(err);
    } finally {
      setIsCancelling(false);
    }
  };

  // Password state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSavingPassword, setIsSavingPassword] = useState(false);

  // Notifications state
  const [criticalAlerts, setCriticalAlerts] = useState(true);
  const [weeklySummary, setWeeklySummary] = useState(false);
  const [isSavingPrefs, setIsSavingPrefs] = useState(false);
  
  // Hidden state to preserve alert threshold
  const [threshold, setThreshold] = useState(3.0);

  // Simulated billing date state
  const [nextBillingDate, setNextBillingDate] = useState('');

  useEffect(() => {
    setNextBillingDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toLocaleDateString());
  }, [user?.subscription_tier]);

  // Load user database preferences
  useEffect(() => {
    if (user?.preferences) {
      if (user.preferences.theme) {
        setTheme(user.preferences.theme);
      }
      if (user.preferences.language) {
        setLanguage(user.preferences.language as Language);
      }
    }
  }, [user, setTheme, setLanguage]);

  // Load alert config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await alertsApi.getConfig();
        setCriticalAlerts(config.notification_email);
        setWeeklySummary(config.notification_push);
        setThreshold(config.high_consumption_threshold);
      } catch (err) {
        console.error('Failed to load alert config:', err);
      }
    };
    loadConfig();
  }, []);

  const handleSavePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error('Please fill in all password fields');
      return;
    }
    if (newPassword.length < 6) {
      toast.error('New password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }
    setIsSavingPassword(true);
    try {
      await authApi.updatePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success('Password updated successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update password');
    } finally {
      setIsSavingPassword(false);
    }
  };

  const handleSavePreferences = async () => {
    setIsSavingPrefs(true);
    try {
      await alertsApi.configureAlerts({
        high_consumption_threshold: threshold,
        anomaly_sensitivity: 'medium',
        notification_email: criticalAlerts,
        notification_push: weeklySummary,
      });

      await settingsApi.updatePreferences({
        theme,
        language,
        email_alerts: criticalAlerts,
        push_alerts: weeklySummary,
      });

      await refreshUser();
      toast.success(t('settings.save') + ' ' + (language === 'en' ? 'successful' : language === 'fr' ? 'réussie' : 'بنجاح'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save preferences');
    } finally {
      setIsSavingPrefs(false);
    }
  };

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">{t('settings.title')}</h1>
          <p className="text-slate-400 mt-1">
            {t('settings.subtitle')}
          </p>
        </div>

        <Tabs defaultValue="preferences" className="w-full">
          <TabsList className="bg-[#111827] border border-white/[0.06] mb-6">
            <TabsTrigger value="preferences" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
              <Bell className="w-4 h-4 mr-2" />
              {t('settings.preferences')}
            </TabsTrigger>
            <TabsTrigger value="security" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
              <Shield className="w-4 h-4 mr-2" />
              {t('settings.security')}
            </TabsTrigger>
            <TabsTrigger value="subscription" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
              <CreditCard className="w-4 h-4 mr-2" />
              Subscription
            </TabsTrigger>
            <TabsTrigger value="models" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
              <Cpu className="w-4 h-4 mr-2" />
              Models
            </TabsTrigger>
          </TabsList>

          {/* Preferences Tab */}
          <TabsContent value="preferences" className="space-y-4">
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-lg text-white">{t('settings.display')}</CardTitle>
                <CardDescription className="text-slate-400">
                  {t('settings.display_desc')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Theme Selection */}
                <div className="space-y-3">
                  <Label className="text-slate-300">{t('settings.theme')}</Label>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      onClick={() => setTheme('light')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${theme === 'light' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <Sun className={`w-6 h-6 mb-2 ${theme === 'light' ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span className={`text-sm ${theme === 'light' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>{t('settings.theme_light')}</span>
                    </button>
                    <button
                      onClick={() => setTheme('dark')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${theme === 'dark' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <Moon className={`w-6 h-6 mb-2 ${theme === 'dark' ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span className={`text-sm ${theme === 'dark' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>{t('settings.theme_dark')}</span>
                    </button>
                    <button
                      onClick={() => setTheme('system')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${theme === 'system' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <Monitor className={`w-6 h-6 mb-2 ${theme === 'system' ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span className={`text-sm ${theme === 'system' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>{t('settings.theme_system')}</span>
                    </button>
                  </div>
                </div>

                {/* Language Selection */}
                <div className="space-y-3 pt-4 border-t border-white/[0.06]">
                  <Label className="text-slate-300 flex items-center gap-2">
                    <Globe className="w-4 h-4 text-blue-400" />
                    {t('settings.language')}
                  </Label>
                  <p className="text-xs text-slate-400 mb-2">{t('settings.language_desc')}</p>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      onClick={() => setLanguage('en')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${language === 'en' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <span className={`text-lg font-bold mb-1 ${language === 'en' ? 'text-blue-400' : 'text-slate-400'}`}>EN</span>
                      <span className={`text-xs ${language === 'en' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>English</span>
                    </button>
                    <button
                      onClick={() => setLanguage('fr')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${language === 'fr' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <span className={`text-lg font-bold mb-1 ${language === 'fr' ? 'text-blue-400' : 'text-slate-400'}`}>FR</span>
                      <span className={`text-xs ${language === 'fr' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>Français</span>
                    </button>
                    <button
                      onClick={() => setLanguage('ar')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${language === 'ar' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <span className={`text-lg font-bold mb-1 ${language === 'ar' ? 'text-blue-400' : 'text-slate-400'}`}>AR</span>
                      <span className={`text-xs ${language === 'ar' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>العربية</span>
                    </button>
                  </div>
                </div>

                {/* Alert Configurations */}
                <div className="space-y-4 pt-4 border-t border-white/[0.06]">
                  <Label className="text-slate-300">{language === 'ar' ? 'إعدادات التنبيه' : language === 'fr' ? 'Configuration des Alertes' : 'Alert Configuration'}</Label>
                  
                  <div className="space-y-2">
                    <Label htmlFor="peak-threshold" className="text-xs text-slate-400">
                      {language === 'ar' ? 'حد الاستهلاك الأقصى (كيلوواط)' : language === 'fr' ? 'Seuil de consommation max (kW)' : 'Peak Consumption Limit (kW)'}
                    </Label>
                    <div className="relative">
                      <Zap className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                      <Input
                        id="peak-threshold"
                        type="number"
                        step="0.1"
                        min="0"
                        value={threshold}
                        onChange={(e) => setThreshold(parseFloat(e.target.value) || 3.0)}
                        className="pl-9 bg-[#0A0F1C] border-white/[0.06] text-white focus:border-blue-500 transition-colors"
                      />
                    </div>
                    <p className="text-[10px] text-slate-500">
                      {language === 'ar' ? 'سيتم تنبيهك إذا تجاوز الاستهلاك الفوري هذا الحد.' : language === 'fr' ? 'Vous serez alerté si la consommation dépasse ce seuil.' : 'You will be alerted if live consumption exceeds this threshold.'}
                    </p>
                  </div>
                  
                  <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 mt-4">
                    <div className="flex items-start gap-2 text-amber-400">
                      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-sm font-medium">{language === 'ar' ? 'تنبيه الميزانية الشهري' : language === 'fr' ? 'Alerte de Budget Mensuel' : 'Monthly Budget Warning'}</p>
                        <p className="text-xs text-amber-500/80 mt-1">
                          {language === 'ar' 
                            ? 'سيتم تنبيهك تلقائيًا إذا كانت تكلفتك المتوقعة تتجاوز 90٪ من ميزانيتك المحددة في لوحة التحكم.' 
                            : language === 'fr' 
                            ? 'Vous serez automatiquement alerté si le coût projeté dépasse 90% de votre budget défini sur le tableau de bord.' 
                            : 'You will automatically be alerted if your projected cost exceeds 90% of your set dashboard budget.'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Notifications */}
                <div className="space-y-4 pt-4 border-t border-white/[0.06]">
                  <Label className="text-slate-300">{t('settings.email_notifs')}</Label>
                  
                  <div className="flex items-center justify-between p-3 rounded-lg border border-white/[0.06] bg-[#0A0F1C]">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded bg-red-500/10 text-red-400">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">{t('settings.critical_alerts')}</p>
                        <p className="text-xs text-slate-400">{t('settings.critical_desc')}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setCriticalAlerts(!criticalAlerts)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${criticalAlerts ? 'bg-blue-500' : 'bg-slate-700'}`}
                    >
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${criticalAlerts ? 'translate-x-4' : 'translate-x-0.5'}`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg border border-white/[0.06] bg-[#0A0F1C]">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded bg-blue-500/10 text-blue-400">
                        <Monitor className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">{t('settings.weekly_summary')}</p>
                        <p className="text-xs text-slate-400">{t('settings.weekly_desc')}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setWeeklySummary(!weeklySummary)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${weeklySummary ? 'bg-blue-500' : 'bg-slate-700'}`}
                    >
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${weeklySummary ? 'translate-x-4' : 'translate-x-0.5'}`} />
                    </button>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/[0.06] flex justify-end">
                  <Button
                    onClick={handleSavePreferences}
                    disabled={isSavingPrefs}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    {isSavingPrefs ? '...' : t('settings.save')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Security Tab */}
          <TabsContent value="security" className="space-y-4">
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-lg text-white">{t('settings.password_title')}</CardTitle>
                <CardDescription className="text-slate-400">
                  {t('settings.password_desc')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSavePassword} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="current-password" className="text-slate-300">{t('settings.current_password')}</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                      <Input
                        id="current-password"
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        className="pl-9 bg-[#0A0F1C] border-white/10 text-white"
                        placeholder="••••••••"
                      />
                    </div>
                  </div>
                  
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="new-password" className="text-slate-300">{t('settings.new_password')}</Label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <Input
                          id="new-password"
                          type="password"
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          className="pl-9 bg-[#0A0F1C] border-white/10 text-white"
                          placeholder="••••••••"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirm-password" className="text-slate-300">{t('settings.confirm_password')}</Label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <Input
                          id="confirm-password"
                          type="password"
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          className="pl-9 bg-[#0A0F1C] border-white/10 text-white"
                          placeholder="••••••••"
                        />
                      </div>
                      {newPassword && confirmPassword && newPassword !== confirmPassword && (
                        <p className="text-xs text-red-400">Passwords do not match</p>
                      )}
                      {newPassword && confirmPassword && newPassword === confirmPassword && (
                        <p className="text-xs text-emerald-400 flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" /> Passwords match
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="pt-4 border-t border-white/[0.06] flex justify-end">
                    <Button
                      type="submit"
                      disabled={isSavingPassword}
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      {isSavingPassword ? '...' : t('settings.update_password')}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Subscription Tab */}
          <TabsContent value="subscription" className="space-y-4">
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-lg text-white">Plan Management</CardTitle>
                <CardDescription className="text-slate-400">
                  Monitor your current subscription tier, active limits, and billing cycle.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between p-6 rounded-2xl border border-white/[0.04] bg-[#0A0F1C]/80 gap-4">
                  <div className="space-y-1">
                    <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Active Plan</p>
                    <div className="flex items-center gap-2 mt-1">
                      <h3 className="text-xl font-bold text-white capitalize">{user?.subscription_tier || 'free'} Plan</h3>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        user?.subscription_tier === 'pro' 
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse'
                          : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                      }`}>
                        {user?.subscription_tier === 'free' || !user?.subscription_tier ? 'Free' : 'Premium'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                      {user?.subscription_tier === 'pro' 
                        ? '99 MAD / month (Advanced AI forecasting & live Linky telemetry enabled)'
                        : '0 MAD / month (Basic CNN-BiLSTM forecasting & 1-hour lookback)'}
                    </p>
                  </div>
                  <div className="flex gap-3 shrink-0 w-full md:w-auto">
                    {user?.subscription_tier && user?.subscription_tier !== 'free' && (
                      <Button
                        variant="outline"
                        onClick={handleCancelSubscription}
                        disabled={isCancelling}
                        className="border-red-500/30 hover:border-red-500/50 text-red-400 hover:text-red-300 hover:bg-red-500/5 py-5 px-5 font-bold text-xs rounded-xl flex-1 md:flex-none"
                      >
                        {isCancelling ? 'Processing...' : 'Cancel Subscription'}
                      </Button>
                    )}
                    <Button
                      onClick={() => router.push('/plans')}
                      className="bg-blue-600 hover:bg-blue-500 text-white py-5 px-5 font-bold text-xs rounded-xl flex-1 md:flex-none"
                    >
                      {user?.subscription_tier === 'free' || !user?.subscription_tier ? 'Upgrade Plan' : 'Change Plan'}
                    </Button>
                  </div>
                </div>

                {/* Simulated Billing Cycle */}
                {user?.subscription_tier && user?.subscription_tier !== 'free' && (
                  <div className="p-4 rounded-xl border border-white/[0.04] bg-[#0A0F1C]/40 text-xs text-slate-400 space-y-2">
                    <div className="flex justify-between">
                      <span>Billing Frequency:</span>
                      <span className="font-medium text-white">Monthly</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Estimated Next Billing Date:</span>
                      <span className="font-medium text-white">
                        {nextBillingDate}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Payment Method:</span>
                      <span className="font-medium text-white">Simulated Billing (Stripe test key)</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Models Tab */}
          <TabsContent value="models" className="space-y-6">
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-lg text-white flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-blue-400" />
                  Default Forecasting Models
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Select which state-of-the-art machine learning model to use for each forecasting horizon by default.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* 24h Horizon Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="model-24h" className="text-slate-300 font-medium">Day Forecast (24 Hours)</Label>
                    <select
                      id="model-24h"
                      value={selectedModel24}
                      onChange={(e) => setSelectedModel24(e.target.value)}
                      className="w-full h-10 px-3 rounded-xl bg-[#0A0F1C] border border-white/[0.08] text-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-sm"
                    >
                      {modelsList.filter(m => {
                        const h = m.parameters?.forecast_horizon;
                        return h?.includes('24') || h?.toLowerCase().includes('day') || (!m.name.includes('_168') && !m.name.includes('_720'));
                      }).map(m => (
                        <option key={m.name} value={m.name} className="bg-[#111827]">{m.display_name}</option>
                      ))}
                    </select>
                  </div>

                  {/* 168h Horizon Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="model-168h" className="text-slate-300 font-medium">Week Forecast (1 Week)</Label>
                    <select
                      id="model-168h"
                      value={selectedModel168}
                      onChange={(e) => setSelectedModel168(e.target.value)}
                      className="w-full h-10 px-3 rounded-xl bg-[#0A0F1C] border border-white/[0.08] text-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-sm"
                    >
                      {modelsList.filter(m => {
                        const h = m.parameters?.forecast_horizon;
                        return h?.includes('168') || h?.toLowerCase().includes('week') || m.name.includes('_168');
                      }).map(m => (
                        <option key={m.name} value={m.name} className="bg-[#111827]">{m.display_name}</option>
                      ))}
                    </select>
                  </div>

                  {/* 720h Horizon Selector */}
                  <div className="space-y-2">
                    <Label htmlFor="model-720h" className="text-slate-300 font-medium">Month Forecast (1 Month)</Label>
                    <select
                      id="model-720h"
                      value={selectedModel720}
                      onChange={(e) => setSelectedModel720(e.target.value)}
                      className="w-full h-10 px-3 rounded-xl bg-[#0A0F1C] border border-white/[0.08] text-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all text-sm"
                    >
                      {modelsList.filter(m => {
                        const h = m.parameters?.forecast_horizon;
                        return h?.includes('720') || h?.toLowerCase().includes('month') || m.name.includes('_720');
                      }).map(m => (
                        <option key={m.name} value={m.name} className="bg-[#111827]">{m.display_name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex justify-end pt-4 border-t border-white/[0.06]">
                  <Button
                    onClick={handleSaveModels}
                    disabled={isSavingModels}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-xl transition-all font-medium text-xs h-10"
                  >
                    {isSavingModels ? "Saving..." : "Save Model Preferences"}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Performance Registry Grid */}
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-yellow-400 animate-pulse" />
                  Model Performance Registry
                </h3>
                <p className="text-sm text-slate-400 mt-1">
                  Inspect the official training accuracy, loss metrics, and architecture configuration parameters for each model.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {modelsList.map((model) => {
                  const is24 = !model.name.includes('_168') && !model.name.includes('_720');
                  const is168 = model.name.includes('_168');
                  const horizonText = is24 ? "24 Hours" : is168 ? "1 Week (168 Hours)" : "1 Month (720 Hours)";
                  const horizonColor = is24 ? "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" : is168 ? "text-purple-400 bg-purple-500/10 border-purple-500/20" : "text-amber-400 bg-amber-500/10 border-amber-500/20";
                  
                  return (
                    <Card key={model.id} className="bg-[#111827]/30 border-white/[0.06] hover:border-white/[0.1] transition-all flex flex-col justify-between">
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-start">
                          <div>
                            <CardTitle className="text-base text-white font-bold">{model.display_name}</CardTitle>
                            <CardDescription className="text-xs text-slate-500 mt-0.5 capitalize">{model.architecture_type} Architecture</CardDescription>
                          </div>
                          <span className={`text-[10px] px-2.5 py-0.5 rounded-full border font-medium ${horizonColor}`}>
                            {horizonText}
                          </span>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4 text-sm pb-5">
                        <p className="text-xs text-slate-400 leading-relaxed">{model.description}</p>
                        
                        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/[0.04]">
                          <div>
                            <span className="text-xs text-slate-500 block">Lookback Window</span>
                            <span className="font-semibold text-slate-300">{model.parameters?.lookback_window || '96 Hours'}</span>
                          </div>
                          <div>
                            <span className="text-xs text-slate-500 block">
                              {model.training_metrics?.r2_score !== undefined ? 'R² Score' : 'Training Accuracy'}
                            </span>
                            <span className="font-semibold text-emerald-400">
                              {model.training_metrics?.r2_score !== undefined 
                                ? model.training_metrics.r2_score.toFixed(4) 
                                : `${model.accuracy}%`}
                            </span>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-white/[0.04] space-y-1.5">
                          <span className="text-xs text-slate-500 block font-medium">Evaluation Metrics</span>
                          <div className="grid grid-cols-4 gap-2 text-xs">
                            <div className="bg-[#0A0F1C]/40 p-1.5 rounded-lg text-center">
                              <span className="text-slate-500 block scale-90">MAE</span>
                              <span className="text-slate-300 font-semibold">{model.training_metrics?.mae?.toFixed(4) || '—'}</span>
                            </div>
                            <div className="bg-[#0A0F1C]/40 p-1.5 rounded-lg text-center">
                              <span className="text-slate-500 block scale-90">RMSE</span>
                              <span className="text-slate-300 font-semibold">{model.training_metrics?.rmse?.toFixed(4) || '—'}</span>
                            </div>
                            <div className="bg-[#0A0F1C]/40 p-1.5 rounded-lg text-center">
                              <span className="text-slate-500 block scale-90">MAPE</span>
                              <span className="text-slate-300 font-semibold">{model.training_metrics?.mape ? `${model.training_metrics.mape.toFixed(2)}%` : '—'}</span>
                            </div>
                            <div className="bg-[#0A0F1C]/40 p-1.5 rounded-lg text-center">
                              <span className="text-slate-500 block scale-90">R²</span>
                              <span className="text-slate-300 font-semibold">{model.training_metrics?.r2_score?.toFixed(4) || '—'}</span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>

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
