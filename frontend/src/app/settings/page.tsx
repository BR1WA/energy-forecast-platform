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
import { authApi, alertsApi, settingsApi } from '@/lib/api';
import { useTheme } from 'next-themes';
import { useI18n, Language } from '@/lib/i18n';
import { toast } from 'sonner';
import { Shield, Bell, Lock, Moon, Sun, Monitor, AlertTriangle, CheckCircle, Globe, CreditCard } from 'lucide-react';

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useI18n();
  const router = useRouter();
  const [isCancelling, setIsCancelling] = useState(false);

  const handleCancelSubscription = async () => {
    if (!confirm("Are you sure you want to cancel your premium subscription? This will immediately downgrade you to the Free plan.")) {
      return;
    }
    setIsCancelling(true);
    try {
      await authApi.updateProfile({ subscription_tier: 'free' });
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
                          : user?.subscription_tier === 'enterprise'
                          ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                          : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                      }`}>
                        {user?.subscription_tier === 'free' || !user?.subscription_tier ? 'Free' : 'Premium'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">
                      {user?.subscription_tier === 'pro' 
                        ? '99 MAD / month (Advanced AI forecasting & live Linky telemetry enabled)'
                        : user?.subscription_tier === 'enterprise'
                        ? '499 MAD / month (Custom ML fine-tuning & multi-site grids enabled)'
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
        </Tabs>
      </div>
    </AppLayout>
  );
}
