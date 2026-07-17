'use client';

import React, { useEffect, useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/lib/auth';
import { authApi, settingsApi } from '@/lib/api';
import { toast } from 'sonner';
import { KeyRound, Settings2, Wallet } from 'lucide-react';

const initialSettings = {
  country: 'Morocco',
  region: 'Casablanca-Settat',
  electricity_provider: 'ONEE',
  currency: 'MAD',
  peak_rate: 1.1,
  off_peak_rate: 0.8,
  peak_start_hour: 6,
  peak_end_hour: 22,
  sensor_type: 'simulator',
  sensor_api_url: null as string | null,
};

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [siteSettings, setSiteSettings] = useState(initialSettings);
  const [budget, setBudget] = useState('400');
  const [saving, setSaving] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');

  useEffect(() => {
    Promise.all([settingsApi.getSettings(), settingsApi.getBudget()])
      .then(([settings, savedBudget]) => {
        setSiteSettings({ ...initialSettings, ...settings });
        if (savedBudget?.monthly_budget_mad) setBudget(String(savedBudget.monthly_budget_mad));
      })
      .catch(() => toast.error('Unable to load site settings.'));
  }, []);

  const saveSiteSettings = async () => {
    setSaving(true);
    try {
      await settingsApi.postSetup(siteSettings);
      await settingsApi.setBudget({ monthly_budget_mad: Number(budget) || 0 });
      await refreshUser();
      toast.success('Settings saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save settings.');
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!currentPassword || newPassword.length < 6) {
      toast.error('Use your current password and a new password of at least 6 characters.');
      return;
    }
    try {
      await authApi.updatePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword('');
      setNewPassword('');
      toast.success('Password updated.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update password.');
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-4xl space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="mt-1 text-sm text-slate-400">Manage your site, budget, and account security.</p>
        </div>
        <Tabs defaultValue="site">
          <TabsList className="border border-white/[0.06] bg-[#111827]">
            <TabsTrigger value="site"><Settings2 className="mr-2 h-4 w-4" />Site</TabsTrigger>
            <TabsTrigger value="budget"><Wallet className="mr-2 h-4 w-4" />Budget</TabsTrigger>
            <TabsTrigger value="security"><KeyRound className="mr-2 h-4 w-4" />Security</TabsTrigger>
          </TabsList>
          <TabsContent value="site" className="mt-6">
            <Card className="border-white/[0.06] bg-[#111827]/50">
              <CardHeader><CardTitle>Site configuration</CardTitle><CardDescription>These values are stored for your own site only.</CardDescription></CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                {([
                  ['country', 'Country'], ['region', 'Region'], ['electricity_provider', 'Provider'], ['currency', 'Currency'],
                ] as const).map(([field, label]) => (
                  <div key={field} className="space-y-2"><Label>{label}</Label><Input value={siteSettings[field]} onChange={(event) => setSiteSettings({ ...siteSettings, [field]: event.target.value })} /></div>
                ))}
                <div className="space-y-2"><Label>Peak rate (MAD/kWh)</Label><Input type="number" value={siteSettings.peak_rate} onChange={(event) => setSiteSettings({ ...siteSettings, peak_rate: Number(event.target.value) })} /></div>
                <div className="space-y-2"><Label>Off-peak rate (MAD/kWh)</Label><Input type="number" value={siteSettings.off_peak_rate} onChange={(event) => setSiteSettings({ ...siteSettings, off_peak_rate: Number(event.target.value) })} /></div>
                <div className="md:col-span-2 flex justify-end"><Button onClick={saveSiteSettings} disabled={saving}>{saving ? 'Saving...' : 'Save site settings'}</Button></div>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="budget" className="mt-6">
            <Card className="border-white/[0.06] bg-[#111827]/50"><CardHeader><CardTitle>Monthly budget</CardTitle><CardDescription>Set the monthly limit used for your budget progress and alerts.</CardDescription></CardHeader><CardContent className="flex max-w-sm items-end gap-3"><div className="flex-1 space-y-2"><Label>Budget (MAD)</Label><Input type="number" min="0" value={budget} onChange={(event) => setBudget(event.target.value)} /></div><Button onClick={saveSiteSettings} disabled={saving}>Save</Button></CardContent></Card>
          </TabsContent>
          <TabsContent value="security" className="mt-6">
            <Card className="border-white/[0.06] bg-[#111827]/50"><CardHeader><CardTitle>Password</CardTitle><CardDescription>Signed in as {user?.email}.</CardDescription></CardHeader><CardContent><form className="max-w-md space-y-4" onSubmit={changePassword}><div className="space-y-2"><Label>Current password</Label><Input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></div><div className="space-y-2"><Label>New password</Label><Input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></div><Button type="submit">Update password</Button></form></CardContent></Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
