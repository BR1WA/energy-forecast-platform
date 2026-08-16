'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/lib/auth';
import { useI18n, type Language } from '@/lib/i18n';
import { API_BASE_URL, accountApi, authApi, ingestionApi, settingsApi } from '@/lib/api';
import { requestGoogleCredential } from '@/lib/google';
import type { PrimaryMeter } from '@/types';
import { toast } from 'sonner';
import { CheckCircle2, Clipboard, Database, KeyRound, Languages, Link2, PlayCircle, Radio, Settings2, Unlink, Upload, Wallet } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import type { AccountDeletionCapabilities } from '@/types';
import {
  MOROCCO_COUNTRY,
  MOROCCO_CURRENCY,
  MOROCCO_REGIONS,
  isMoroccoRegion,
  type MoroccoRegion,
} from '@/lib/morocco';

const initialSettings = {
  country: 'Morocco',
  region: 'Casablanca-Settat',
  electricity_provider: null as string | null,
  currency: 'MAD',
  peak_rate: 1.1,
  off_peak_rate: 0.8,
  peak_start_hour: 6,
  peak_end_hour: 22,
  sensor_type: 'simulator',
};

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { language, setLanguage, t } = useI18n();
  const [siteSettings, setSiteSettings] = useState(initialSettings);
  const [budget, setBudget] = useState('400');
  const [saving, setSaving] = useState(false);
  const [budgetSaving, setBudgetSaving] = useState(false);
  const [languageSaving, setLanguageSaving] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [deletionPassword, setDeletionPassword] = useState('');
  const [deletionConfirmation, setDeletionConfirmation] = useState('');
  const [deletionCapabilities, setDeletionCapabilities] = useState<AccountDeletionCapabilities | null>(null);
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('site');
  const [meter, setMeter] = useState<PrimaryMeter | null>(null);
  const [meterInterval, setMeterInterval] = useState('60');
  const [pushKey, setPushKey] = useState<string | null>(null);
  const [meterSaving, setMeterSaving] = useState(false);
  const [pushTesting, setPushTesting] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [googleLinked, setGoogleLinked] = useState(false);
  const [googleCanUnlink, setGoogleCanUnlink] = useState(false);
  const [googlePassword, setGooglePassword] = useState('');
  const [googleSaving, setGoogleSaving] = useState(false);

  useEffect(() => {
    Promise.all([settingsApi.getSettings(), settingsApi.getBudget(), ingestionApi.getMeters(), accountApi.getDeletionCapabilities()])
      .then(([settings, savedBudget, meters, deletion]) => {
        setSiteSettings({
          country: MOROCCO_COUNTRY,
          region: isMoroccoRegion(settings.region) ? settings.region : 'Casablanca-Settat',
          electricity_provider: null,
          currency: MOROCCO_CURRENCY,
          peak_rate: settings.peak_rate,
          off_peak_rate: settings.off_peak_rate,
          peak_start_hour: settings.peak_start_hour,
          peak_end_hour: settings.peak_end_hour,
          sensor_type: settings.sensor_type,
        });
        if (savedBudget !== null) setBudget(String(savedBudget.monthly_budget_mad));
        const primary = meters[0] ?? null;
        setMeter(primary);
        setMeterInterval(String(primary?.expected_interval_seconds ?? 60));
        setDeletionCapabilities(deletion);
      })
      .catch(() => toast.error('Unable to load site settings.'));
    const requestedTab = new URLSearchParams(window.location.search).get('tab');
    const tabTimer = requestedTab && ['site', 'data', 'budget', 'preferences', 'security'].includes(requestedTab)
      ? window.setTimeout(() => setActiveTab(requestedTab), 0)
      : null;
    authApi.getCapabilities()
      .then(async (capabilities) => {
        const browserClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
        const enabled = Boolean(capabilities.google_auth_enabled && browserClientId && capabilities.google_client_id === browserClientId);
        setGoogleEnabled(enabled);
        if (enabled) {
          const identity = await authApi.googleStatus();
          setGoogleLinked(identity.linked);
          setGoogleCanUnlink(identity.can_unlink);
        }
      })
      .catch(() => setGoogleEnabled(false));
    return () => {
      if (tabTimer !== null) window.clearTimeout(tabTimer);
    };
  }, []);

  const refreshMeter = async () => {
    const primary = (await ingestionApi.getMeters())[0] ?? null;
    setMeter(primary);
    setMeterInterval(String(primary?.expected_interval_seconds ?? 60));
  };

  const saveMeter = async () => {
    if (!meter) return;
    const interval = Number(meterInterval);
    if (!Number.isInteger(interval) || interval < 5 || interval > 86400) {
      toast.error('Expected interval must be between 5 seconds and 24 hours.');
      return;
    }
    setMeterSaving(true);
    try {
      await ingestionApi.updateMeter(meter.id, { expected_interval_seconds: interval });
      await refreshMeter();
      toast.success('Meter cadence saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update the meter.');
    } finally {
      setMeterSaving(false);
    }
  };

  const rotatePushKey = async () => {
    if (!meter) return;
    if (meter.push_key_configured && !window.confirm('Rotate the meter key? The existing device key will stop working immediately.')) return;
    try {
      const result = await ingestionApi.rotatePushKey(meter.id);
      setPushKey(result.api_key);
      await refreshMeter();
      toast.success('New key generated. The previous key is no longer valid.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to generate a push key.');
    }
  };

  const copyPushKey = async () => {
    if (!pushKey) return;
    await navigator.clipboard.writeText(pushKey);
    toast.success('Meter key copied.');
  };

  const sendTestReading = async () => {
    if (!meter || !pushKey) {
      toast.error('Generate a new key in this session before sending a test reading.');
      return;
    }
    setPushTesting(true);
    try {
      const result = await ingestionApi.sendTestReading(meter.id, pushKey);
      await refreshMeter();
      if (result.accepted_rows === 1) toast.success('Test reading accepted. It is now available in Live mode.');
      else toast.error(result.rejected_rows ? 'The test reading was rejected.' : 'The test reading was not added.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Test push failed.');
    } finally {
      setPushTesting(false);
    }
  };

  const saveSiteSettings = async () => {
    setSaving(true);
    try {
      await settingsApi.postSetup({
        region: siteSettings.region,
        peak_rate: siteSettings.peak_rate,
        off_peak_rate: siteSettings.off_peak_rate,
        peak_start_hour: siteSettings.peak_start_hour,
        peak_end_hour: siteSettings.peak_end_hour,
        sensor_type: siteSettings.sensor_type,
      });
      await refreshUser();
      toast.success('Site settings saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save settings.');
    } finally {
      setSaving(false);
    }
  };

  const saveBudget = async () => {
    const numericBudget = Number(budget);
    if (!Number.isFinite(numericBudget) || numericBudget < 0) {
      toast.error('Budget must be a non-negative number.');
      return;
    }
    setBudgetSaving(true);
    try {
      const savedBudget = await settingsApi.setBudget({ monthly_budget_mad: numericBudget });
      setBudget(String(savedBudget.monthly_budget_mad));
      toast.success('Monthly budget saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save the budget.');
    } finally {
      setBudgetSaving(false);
    }
  };

  const saveLanguage = async (nextLanguage: Language) => {
    setLanguage(nextLanguage);
    setLanguageSaving(true);
    try {
      await settingsApi.updatePreferences({ language: nextLanguage });
      await refreshUser();
      toast.success('Language preference saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save the language preference.');
    } finally {
      setLanguageSaving(false);
    }
  };

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!currentPassword || newPassword.length < 12) {
      toast.error('Use your current password and a new password of at least 12 characters.');
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

  const linkGoogle = async () => {
    const browserClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!browserClientId || !googlePassword) {
      toast.error('Enter your current password before linking Google.');
      return;
    }
    setGoogleSaving(true);
    try {
      const challenge = await authApi.googleLinkChallenge();
      const credential = await requestGoogleCredential(browserClientId, challenge.nonce);
      const result = await authApi.linkGoogle(credential, challenge.state, googlePassword);
      setGoogleLinked(true);
      setGoogleCanUnlink(true);
      setGooglePassword('');
      toast.success(result.message);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to link Google.');
    } finally {
      setGoogleSaving(false);
    }
  };

  const unlinkGoogle = async () => {
    if (!googlePassword) {
      toast.error('Enter your current password before unlinking Google.');
      return;
    }
    setGoogleSaving(true);
    try {
      const result = await authApi.unlinkGoogle(googlePassword);
      toast.success(result.message);
      window.location.href = '/login';
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to unlink Google.');
      setGoogleSaving(false);
    }
  };

  const exportAccount = async () => {
    try {
      const blob = await accountApi.exportData();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `energyforecast-account-${new Date().toISOString().slice(0, 10)}.zip`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to export account data.');
    }
  };

  const deleteAccount = async () => {
    if (deletionConfirmation !== 'DELETE') {
      toast.error('Type DELETE to confirm permanent account deletion.');
      return;
    }
    if (!deletionCapabilities || !window.confirm('Permanently delete this account, its readings, forecasts, alerts, and avatar? This cannot be undone.')) return;
    setDeletingAccount(true);
    try {
      if (deletionCapabilities.method === 'password') {
        if (!deletionPassword) throw new Error('Enter your current password.');
        await accountApi.deleteWithPassword(deletionPassword);
      } else {
        const browserClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
        if (!browserClientId || !deletionCapabilities.google_reauthentication_available) {
          throw new Error('Google reauthentication is not currently available.');
        }
        const challenge = await accountApi.deletionChallenge();
        const credential = await requestGoogleCredential(browserClientId, challenge.nonce);
        await accountApi.deleteWithGoogle(credential, challenge.state);
      }
      window.location.href = '/login';
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to delete account.');
      setDeletingAccount(false);
    }
  };

  const uploadAvatar = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setAvatarSaving(true);
    try {
      await authApi.uploadAvatar(file);
      await refreshUser();
      toast.success('Avatar updated.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update avatar.');
    } finally {
      setAvatarSaving(false);
    }
  };

  const deleteAvatar = async () => {
    setAvatarSaving(true);
    try {
      await authApi.deleteAvatar();
      await refreshUser();
      toast.success('Avatar removed.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to remove avatar.');
    } finally {
      setAvatarSaving(false);
    }
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="mt-1 text-sm text-slate-400">Manage your site, budget, and account security.</p>
        </div>
        <Tabs onValueChange={(value) => setActiveTab(String(value))} value={activeTab}>
          <TabsList className="max-w-full overflow-x-auto border border-white/[0.06] bg-[#111827]">
            <TabsTrigger value="site"><Settings2 className="mr-2 h-4 w-4" />Site</TabsTrigger>
            <TabsTrigger value="data"><Database className="mr-2 h-4 w-4" />Data sources</TabsTrigger>
            <TabsTrigger value="budget"><Wallet className="mr-2 h-4 w-4" />Budget</TabsTrigger>
            <TabsTrigger value="preferences"><Languages className="mr-2 h-4 w-4" />{t('settings.preferences')}</TabsTrigger>
            <TabsTrigger value="security"><KeyRound className="mr-2 h-4 w-4" />Security</TabsTrigger>
          </TabsList>
          <TabsContent value="site" className="mt-6">
            <Card className="border-white/[0.06] bg-[#111827]/50">
              <CardHeader><CardTitle>Site configuration</CardTitle><CardDescription>These values are stored for your own site only.</CardDescription></CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2"><Label htmlFor="site-region">Region</Label><select id="site-region" className="flex h-9 w-full rounded-lg border border-input bg-transparent px-3 py-1 text-sm text-white outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" value={siteSettings.region} onChange={(event) => setSiteSettings({ ...siteSettings, region: event.target.value as MoroccoRegion })}>{MOROCCO_REGIONS.map((option) => <option className="bg-[#111827]" key={option} value={option}>{option}</option>)}</select></div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-white/10 bg-slate-950/30 p-3"><p className="text-xs text-slate-500">Country</p><p className="mt-1 text-sm font-medium text-white">{MOROCCO_COUNTRY}</p></div>
                  <div className="rounded-lg border border-white/10 bg-slate-950/30 p-3"><p className="text-xs text-slate-500">Currency</p><p className="mt-1 text-sm font-medium text-white">{MOROCCO_CURRENCY}</p></div>
                </div>
                <div className="space-y-2"><Label htmlFor="site-peak-rate">Peak rate (MAD/kWh)</Label><Input id="site-peak-rate" type="number" value={siteSettings.peak_rate} onChange={(event) => setSiteSettings({ ...siteSettings, peak_rate: Number(event.target.value) })} /></div>
                <div className="space-y-2"><Label htmlFor="site-off-peak-rate">Off-peak rate (MAD/kWh)</Label><Input id="site-off-peak-rate" type="number" value={siteSettings.off_peak_rate} onChange={(event) => setSiteSettings({ ...siteSettings, off_peak_rate: Number(event.target.value) })} /></div>
                <p className="text-xs leading-5 text-slate-500 md:col-span-2">This Morocco-focused workspace uses Africa/Casablanca and MAD. Provider is not requested because it does not affect the configurable tariff estimate; region is retained as site metadata and is not currently sent to a weather API.</p>
                <div className="md:col-span-2 flex justify-end"><Button onClick={saveSiteSettings} disabled={saving}>{saving ? 'Saving...' : 'Save site settings'}</Button></div>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="data" className="mt-6 space-y-5">
            <Card className="rounded-lg border-white/[0.06] bg-[#111827]">
              <CardHeader><CardTitle className="flex items-center gap-2"><Radio className="h-4 w-4 text-cyan-400" />Primary meter</CardTitle><CardDescription>All monitoring and forecasting use this single meter.</CardDescription></CardHeader>
              <CardContent className="space-y-4">
                {!meter ? <p className="text-sm text-amber-300">The primary meter is unavailable. Complete setup or reload this page.</p> : <>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div><p className="text-xs text-slate-500">Name</p><p className="mt-1 text-sm text-white">{meter.name}</p></div>
                    <div><p className="text-xs text-slate-500">Current source</p><p className="mt-1 text-sm capitalize text-white">{meter.source_type}</p></div>
                    <div><p className="text-xs text-slate-500">Last reading</p><p className="mt-1 text-sm text-white">{meter.last_seen_at ? new Date(meter.last_seen_at).toLocaleString() : 'No readings yet'}</p></div>
                  </div>
                  <div className="flex max-w-md items-end gap-3"><div className="flex-1 space-y-2"><Label>Expected reading interval (seconds)</Label><Input max="86400" min="5" onChange={(event) => setMeterInterval(event.target.value)} type="number" value={meterInterval} /></div><Button disabled={meterSaving} onClick={saveMeter}>{meterSaving ? 'Saving...' : 'Save'}</Button></div>
                </>}
              </CardContent>
            </Card>

            <Card className="rounded-lg border-white/[0.06] bg-[#111827]">
              <CardHeader><CardTitle>Push API connection</CardTitle><CardDescription>Generate a device key and send readings directly from your meter or gateway.</CardDescription></CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-center gap-2"><Button disabled={!meter} onClick={rotatePushKey}><KeyRound />{meter?.push_key_configured ? 'Rotate key' : 'Generate key'}</Button>{meter?.push_key_configured && <span className="inline-flex items-center gap-1 text-xs text-emerald-300"><CheckCircle2 className="h-3.5 w-3.5" />A push key is configured</span>}</div>
                {pushKey && <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3"><p className="text-xs text-amber-200">This key is shown once. Store it in the device configuration before leaving this page.</p><div className="flex gap-2"><Input aria-label="New meter key" className="font-mono text-xs" readOnly value={pushKey} /><Button aria-label="Copy meter key" onClick={copyPushKey} size="icon" title="Copy key" variant="outline"><Clipboard /></Button></div></div>}
                <div className="overflow-x-auto rounded-lg border border-white/10 bg-slate-950 p-3 font-mono text-xs text-slate-300"><pre>{`POST ${API_BASE_URL}/api/v1/ingestion/meters/${meter?.id ?? '{meter_id}'}/samples\nX-Meter-Key: YOUR_METER_KEY\n\n{"idempotency_key":"device-batch-0001","samples":[{"timestamp":"CURRENT_ISO_8601_TIME_WITH_OFFSET","active_power_kw":1.25,"voltage_v":230}]}`}</pre></div>
                <Button disabled={!pushKey || pushTesting} onClick={sendTestReading} variant="outline">{pushTesting ? 'Sending...' : 'Send a 0.5 kW test reading'}</Button>
              </CardContent>
            </Card>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="border-t border-white/10 pt-4"><Upload className="h-5 w-5 text-cyan-400" /><h3 className="mt-2 font-medium text-white">CSV history</h3><p className="mt-1 text-xs text-slate-400">Preview and import up to 10,000 validated historical readings.</p><Link className={buttonVariants({ size: 'sm', variant: 'outline', className: 'mt-3' })} href="/usage">Open Usage import</Link></div>
              <div className="border-t border-white/10 pt-4"><PlayCircle className="h-5 w-5 text-emerald-400" /><h3 className="mt-2 font-medium text-white">Demo simulator</h3><p className="mt-1 text-xs text-slate-400">Start or stop clearly labelled simulated readings yourself.</p><Link className={buttonVariants({ size: 'sm', variant: 'outline', className: 'mt-3' })} href="/simulation">Open simulator</Link></div>
            </div>
          </TabsContent>
          <TabsContent value="budget" className="mt-6">
            <Card className="border-white/[0.06] bg-[#111827]/50"><CardHeader><CardTitle>Monthly budget</CardTitle><CardDescription>Set the monthly limit used for your budget progress and alerts.</CardDescription></CardHeader><CardContent className="flex max-w-sm items-end gap-3"><div className="flex-1 space-y-2"><Label htmlFor="monthly-budget">Budget (MAD)</Label><Input id="monthly-budget" type="number" min="0" value={budget} onChange={(event) => setBudget(event.target.value)} /></div><Button onClick={saveBudget} disabled={budgetSaving}>{budgetSaving ? 'Saving...' : 'Save budget'}</Button></CardContent></Card>
          </TabsContent>
          <TabsContent value="preferences" className="mt-6">
            <Card className="border-white/[0.06] bg-[#111827]/50">
              <CardHeader><CardTitle>{t('settings.display')}</CardTitle><CardDescription>{t('settings.language_desc')}</CardDescription></CardHeader>
              <CardContent className="max-w-sm space-y-2">
                <Label htmlFor="language-preference">{t('settings.language')}</Label>
                <select
                  id="language-preference"
                  className="flex h-9 w-full rounded-lg border border-input bg-transparent px-3 py-1 text-sm text-white outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                  disabled={languageSaving}
                  onChange={(event) => void saveLanguage(event.target.value as Language)}
                  value={language}
                >
                  <option className="bg-[#111827]" value="en">English</option>
                  <option className="bg-[#111827]" value="fr">Français</option>
                  <option className="bg-[#111827]" value="ar">العربية</option>
                </select>
                {languageSaving ? <p className="text-xs text-slate-400">Saving preference...</p> : null}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="security" className="mt-6">
            <div className="space-y-4">
              <Card className="border-white/[0.06] bg-[#111827]/50"><CardHeader><CardTitle>Profile image</CardTitle><CardDescription>JPEG, PNG, WebP, HEIC, or HEIF up to 2 MB and 2048 pixels per side. Images are normalized to a safe web format.</CardDescription></CardHeader><CardContent className="flex flex-wrap items-center gap-4"><Avatar className="h-16 w-16">{user?.avatar_url ? <AvatarImage alt={user.full_name || 'Account avatar'} className="object-cover" src={user.avatar_url.startsWith('http') ? user.avatar_url : `${API_BASE_URL}${user.avatar_url}`} /> : null}<AvatarFallback>{user?.full_name?.slice(0, 2).toUpperCase() || 'U'}</AvatarFallback></Avatar><div className="flex flex-wrap gap-2"><Label className={buttonVariants({ variant: 'outline' })} htmlFor="avatar-upload">{avatarSaving ? 'Working…' : user?.avatar_url ? 'Replace avatar' : 'Upload avatar'}</Label><Input accept="image/jpeg,image/png,image/webp,image/heic,image/heif" className="sr-only" disabled={avatarSaving} id="avatar-upload" onChange={uploadAvatar} type="file" />{user?.avatar_url ? <Button disabled={avatarSaving} onClick={deleteAvatar} type="button" variant="outline">Remove avatar</Button> : null}</div></CardContent></Card>
              <Card className="border-white/[0.06] bg-[#111827]/50"><CardHeader><CardTitle>Password</CardTitle><CardDescription>Signed in as {user?.email}.</CardDescription></CardHeader><CardContent><form className="max-w-md space-y-4" onSubmit={changePassword}><div className="space-y-2"><Label>Current password</Label><Input type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></div><div className="space-y-2"><Label>New password</Label><Input type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></div><Button type="submit">Update password</Button></form></CardContent></Card>
              {googleEnabled ? <Card className="border-white/[0.06] bg-[#111827]/50"><CardHeader><CardTitle>Google sign-in</CardTitle><CardDescription>{googleLinked ? 'Google is linked. Unlinking revokes every active session.' : 'Link the Google account with the same verified email.'}</CardDescription></CardHeader><CardContent className="max-w-md space-y-4"><div className="space-y-2"><Label htmlFor="google-current-password">Current password</Label><Input id="google-current-password" autoComplete="current-password" onChange={(event) => setGooglePassword(event.target.value)} type="password" value={googlePassword} /></div>{googleLinked ? <Button disabled={googleSaving || !googleCanUnlink} onClick={unlinkGoogle} variant="destructive"><Unlink />{googleSaving ? 'Unlinking...' : 'Unlink Google'}</Button> : <Button disabled={googleSaving} onClick={linkGoogle}><Link2 />{googleSaving ? 'Linking...' : 'Link Google'}</Button>}{googleLinked && !googleCanUnlink ? <p className="text-xs text-amber-300">Set a local password before removing your last usable sign-in method.</p> : null}</CardContent></Card> : null}
              <Card className="border-red-500/20 bg-[#111827]/50"><CardHeader><CardTitle>Privacy controls</CardTitle><CardDescription>Download a complete machine-readable archive before permanently deleting the account.</CardDescription></CardHeader><CardContent className="space-y-5"><Button onClick={exportAccount} variant="outline">Download account archive</Button><div className="max-w-md space-y-3 border-t border-red-500/20 pt-4"><p className="text-xs leading-5 text-red-200">Deletion removes owned readings, forecasts, alerts, recommendations, configuration, sessions, and the avatar. It cannot be undone.</p>{deletionCapabilities?.method === 'password' ? <Input aria-label="Password to delete account" autoComplete="current-password" onChange={(event) => setDeletionPassword(event.target.value)} placeholder="Current password" type="password" value={deletionPassword} /> : <p className="text-xs text-slate-400">Google will ask you to reauthenticate before deletion.</p>}<Input aria-label="Type DELETE to confirm" autoComplete="off" onChange={(event) => setDeletionConfirmation(event.target.value)} placeholder="Type DELETE" value={deletionConfirmation} /><Button disabled={deletingAccount || deletionConfirmation !== 'DELETE'} onClick={deleteAccount} variant="destructive">{deletingAccount ? 'Deleting permanently…' : 'Permanently delete account'}</Button></div></CardContent></Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  );
}
