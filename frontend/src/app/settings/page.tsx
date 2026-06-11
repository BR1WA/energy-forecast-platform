'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/lib/auth';
import { authApi, alertsApi } from '@/lib/api';
import { useTheme } from 'next-themes';
import { toast } from 'sonner';
import { Shield, Bell, Lock, Moon, Sun, Monitor, AlertTriangle, CheckCircle } from 'lucide-react';

export default function SettingsPage() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();

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
      toast.success('Preferences saved successfully');
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
          <h1 className="text-2xl font-bold text-white tracking-tight">Account Settings</h1>
          <p className="text-slate-400 mt-1">
            Manage your profile, preferences, and security settings.
          </p>
        </div>

        <Tabs defaultValue="preferences" className="w-full">
          <TabsList className="bg-[#111827] border border-white/[0.06] mb-6">
            <TabsTrigger value="preferences" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
              <Bell className="w-4 h-4 mr-2" />
              Preferences
            </TabsTrigger>
            <TabsTrigger value="security" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">
              <Shield className="w-4 h-4 mr-2" />
              Security
            </TabsTrigger>
          </TabsList>

          {/* Preferences Tab */}
          <TabsContent value="preferences" className="space-y-4">
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-lg text-white">Display & Notifications</CardTitle>
                <CardDescription className="text-slate-400">
                  Customize how EnergyAI looks and communicates with you.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Theme Selection */}
                <div className="space-y-3">
                  <Label className="text-slate-300">Theme Preference</Label>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      onClick={() => setTheme('light')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${theme === 'light' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <Sun className={`w-6 h-6 mb-2 ${theme === 'light' ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span className={`text-sm ${theme === 'light' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>Light</span>
                    </button>
                    <button
                      onClick={() => setTheme('dark')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${theme === 'dark' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <Moon className={`w-6 h-6 mb-2 ${theme === 'dark' ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span className={`text-sm ${theme === 'dark' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>Dark</span>
                    </button>
                    <button
                      onClick={() => setTheme('system')}
                      className={`flex flex-col items-center justify-center p-4 rounded-xl border ${theme === 'system' ? 'border-blue-500 bg-blue-500/10' : 'border-white/[0.06] bg-[#0A0F1C] hover:bg-white/[0.04]'} transition-all`}
                    >
                      <Monitor className={`w-6 h-6 mb-2 ${theme === 'system' ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span className={`text-sm ${theme === 'system' ? 'text-blue-400 font-medium' : 'text-slate-400'}`}>System</span>
                    </button>
                  </div>
                </div>

                {/* Notifications */}
                <div className="space-y-4 pt-4 border-t border-white/[0.06]">
                  <Label className="text-slate-300">Email Notifications</Label>
                  
                  <div className="flex items-center justify-between p-3 rounded-lg border border-white/[0.06] bg-[#0A0F1C]">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded bg-red-500/10 text-red-400">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">Critical Alerts</p>
                        <p className="text-xs text-slate-400">Receive emails for peak consumption warnings</p>
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
                        <p className="text-sm font-medium text-white">Weekly Summary</p>
                        <p className="text-xs text-slate-400">Receive a weekly digest of your energy usage</p>
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
                    {isSavingPrefs ? 'Saving...' : 'Save Preferences'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Security Tab */}
          <TabsContent value="security" className="space-y-4">
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-lg text-white">Security Settings</CardTitle>
                <CardDescription className="text-slate-400">
                  Manage your password and account security.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSavePassword} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="current-password" className="text-slate-300">Current Password</Label>
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
                      <Label htmlFor="new-password" className="text-slate-300">New Password</Label>
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
                      <Label htmlFor="confirm-password" className="text-slate-300">Confirm New Password</Label>
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
                      {isSavingPassword ? 'Updating...' : 'Update Password'}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
