'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Bell,
  AlertTriangle,
  Info,
  CheckCircle2,
  Settings,
  Filter,
  Zap,
  TrendingUp,
  ShieldAlert,
  Loader2,
} from 'lucide-react';
import { alertsApi } from '@/lib/api';
import { parseDate } from '@/lib/utils';
import { Alert } from '@/types';
import { toast } from 'sonner';

const notificationConfig: Record<string, any> = {
  critical: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    icon: ShieldAlert,
  },
  warning: {
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    icon: AlertTriangle,
  },
  info: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    icon: Info,
  },
  success: {
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    icon: CheckCircle2,
  }
};

const notificationReferenceTime = Date.now();

export default function AlertsPage() {
  const [filter, setFilter] = useState('all');
  const [threshold, setThreshold] = useState('3.0');
  const [sensitivity, setSensitivity] = useState('medium');
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [pushEnabled, setPushEnabled] = useState(true);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Listen for real-time alerts broadcasted via custom event from Navbar (deduplicated)
  useEffect(() => {
    const handleNewAlert = (e: Event) => {
      try {
        const payload = (e as CustomEvent).detail;
        if (payload && payload.type === 'alert') {
          const mappedAlert: Alert = {
            id: payload.id || String(Date.now()),
            type: payload.alert_type as any || 'peak_demand',
            severity: payload.severity || 'medium',
            title: payload.title || 'Peak Consumption Warning',
            message: payload.message || '',
            is_read: false,
            created_at: payload.created_at || new Date().toISOString(),
          };
          setAlerts((prev) => {
            if (prev.some(a => a.id === mappedAlert.id)) return prev;
            return [mappedAlert, ...prev];
          });
        }
      } catch (err) {
        console.error('[Event] Error handling new alert event:', err);
      }
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('app-alert-received', handleNewAlert);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('app-alert-received', handleNewAlert);
      }
    };
  }, []);

  useEffect(() => {
    const fetchAlertsAndConfig = async () => {
      try {
        const [fetchedAlerts, config] = await Promise.all([
          alertsApi.getAlerts(),
          alertsApi.getConfig(),
        ]);
        // Sort by created_at desc
        const sorted = fetchedAlerts.sort((a, b) => parseDate(b.created_at).getTime() - parseDate(a.created_at).getTime());
        setAlerts(sorted);
        if (config) {
          setThreshold(String(config.high_consumption_threshold));
          setSensitivity(config.anomaly_sensitivity);
          setEmailEnabled(config.notification_email);
          setPushEnabled(config.notification_push);
        }
      } catch (err) {
        console.error('Failed to fetch alerts and config', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAlertsAndConfig();
  }, []);

  const handleAcknowledge = async (id: string) => {
    try {
      await alertsApi.acknowledgeAlert(id);
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, is_read: true, is_acknowledged: true } : a))
      );
    } catch (err) {
      console.error('Failed to acknowledge alert', err);
    }
  };

  const handleSaveConfig = async () => {
    setSaving(true);
    try {
      await alertsApi.configureAlerts({
        high_consumption_threshold: parseFloat(threshold),
        anomaly_sensitivity: sensitivity as 'low' | 'medium' | 'high',
        notification_email: emailEnabled,
        notification_push: pushEnabled,
      });
      toast.success('Configuration saved successfully');
    } catch (err) {
      console.error('Failed to save config', err);
      toast.error('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'all') return true;
    if (filter === 'unread') return !a.is_read && !(a as any).is_acknowledged;
    return a.severity === filter;
  });

  const unreadCount = alerts.filter((a) => !a.is_read && !(a as any).is_acknowledged).length;

  const buildNotificationsList = () => {
    const list = filteredAlerts.map(a => {
      const isRead = a.is_read || (a as any).is_acknowledged;
      return {
        id: a.id,
        type: a.type,
        severity: a.severity === 'high' || a.severity === 'critical' ? 'critical' : 'warning',
        title: a.title || a.type.replace(/_/g, ' ').toUpperCase(),
        message: a.message,
        isRead,
        createdAt: parseDate(a.created_at),
        category: 'alert'
      };
    });

    if (filter === 'all' || filter === 'low') {
      list.push({
        id: 'notif-1',
        type: 'goal_achieved' as any,
        severity: 'success',
        title: 'Goal Achieved: Budget Target Met!',
        message: 'Your household consumption remained below the 400 MAD budget threshold this week.',
        isRead: true,
        createdAt: new Date(notificationReferenceTime - 3600000 * 2),
        category: 'success'
      });
      list.push({
        id: 'notif-2',
        type: 'simulation_finished' as any,
        severity: 'info',
        title: 'Virtual House Simulator Active',
        message: 'A new simulation scenario was executed. Baseline load metrics updated.',
        isRead: true,
        createdAt: new Date(notificationReferenceTime - 3600000 * 6),
        category: 'info'
      });
      list.push({
        id: 'notif-3',
        type: 'recommendation_generated' as any,
        severity: 'info',
        title: 'New AI Saving Recommendation',
        message: 'Peak load shifts detected: Delaying laundry to off-peak slots can save up to 9 MAD.',
        isRead: true,
        createdAt: new Date(notificationReferenceTime - 3600000 * 12),
        category: 'info'
      });
    }

    return list.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
  };

  const notifications = buildNotificationsList();

  return (
    <AppLayout>
      <div className="space-y-6 max-w-7xl mx-auto p-2">
        {/* Onboarding Flow Stepper */}
        <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md overflow-hidden relative">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-indigo-500 to-blue-400" />
          <CardContent className="p-5">
            <p className="text-xs font-bold text-indigo-400 uppercase tracking-widest mb-4">First-Run Onboarding Flow</p>
            <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-center md:text-left">
              {/* Step 1 */}
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">1</div>
                <div>
                  <p className="text-xs font-semibold text-white">Create Household</p>
                  <p className="text-[10px] text-emerald-400">Completed ✓</p>
                </div>
              </div>
              <div className="hidden md:block text-slate-600">→</div>
              {/* Step 2 */}
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">2</div>
                <div>
                  <p className="text-xs font-semibold text-white">Connect Smart Meter</p>
                  <p className="text-[10px] text-emerald-400">Connected ✓</p>
                </div>
              </div>
              <div className="hidden md:block text-slate-600">→</div>
              {/* Step 3 */}
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">3</div>
                <div>
                  <p className="text-xs font-semibold text-white">Import History</p>
                  <p className="text-[10px] text-indigo-400 font-bold animate-pulse">Importing...</p>
                </div>
              </div>
              <div className="hidden md:block text-slate-600">→</div>
              {/* Step 4 */}
              <div className="flex items-center gap-3 opacity-50">
                <div className="w-7 h-7 rounded-full bg-white/10 text-slate-400 font-bold text-xs flex items-center justify-center">4</div>
                <div>
                  <p className="text-xs font-semibold text-slate-400">Dashboard Ready</p>
                  <p className="text-[10px] text-slate-500">Pending</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-2">
              <Bell className="w-8 h-8 text-indigo-400" />
              Notifications & Alerts
            </h1>
            <p className="text-slate-400 mt-1">
              Unified timeline matching anomalies, recommendations, and goals progression.
            </p>
          </div>
          <Badge
            className={`${
              unreadCount > 0
                ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/20'
                : 'bg-white/[0.04] text-slate-400 border-white/[0.06]'
            }`}
          >
            {unreadCount} unread
          </Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Notifications Timeline (Col 1 & 2) */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filter Bar */}
            <Card className="glass-card border-white/10">
              <CardContent className="p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <Filter className="w-4 h-4 text-slate-500" />
                  {['all', 'unread', 'critical', 'warning', 'info', 'success'].map(
                    (f) => (
                      <button
                        key={f}
                        id={`filter-${f}`}
                        onClick={() => setFilter(f)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 capitalize ${
                          filter === f
                            ? 'bg-indigo-600/25 text-indigo-400 border border-indigo-500/20'
                            : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
                        }`}
                      >
                        {f}
                      </button>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Timeline Items */}
            <div className="space-y-3 relative before:absolute before:inset-y-0 before:left-8 before:w-0.5 before:bg-white/5">
              {loading ? (
                <div className="flex justify-center p-8">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                </div>
              ) : notifications.length > 0 ? (
                notifications.map((notif) => {
                  const isRead = notif.isRead;
                  const config = notificationConfig[notif.severity] || notificationConfig.info;
                  const Icon = config.icon;
                  return (
                    <Card
                      key={notif.id}
                      id={`notification-${notif.id}`}
                      className={`bg-[#111827]/85 border-white/10 hover:border-indigo-500/20 transition-all duration-200 relative z-10 ${
                        !isRead ? 'ring-1 ring-indigo-500/20' : ''
                      }`}
                    >
                      <CardContent className="p-4">
                        <div className="flex gap-4">
                          <div
                            className={`flex items-center justify-center w-8 h-8 rounded-lg ${config.bg} shrink-0 mt-0.5`}
                          >
                            <Icon className={`w-4 h-4 ${config.color}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="flex items-center gap-2">
                                  <h3 className="text-sm font-semibold text-white">
                                    {notif.title}
                                  </h3>
                                  {!isRead && (
                                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                                  )}
                                </div>
                                <p className="text-xs text-slate-400 mt-1">
                                  {notif.message}
                                </p>
                              </div>
                              <Badge
                                variant="outline"
                                className={`${config.color} border-current/15 text-[9px] uppercase shrink-0 px-2`}
                              >
                                {notif.severity}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-3 mt-3">
                              <span className="text-[10px] text-slate-500 font-mono">
                                {notif.createdAt.toLocaleString()}
                              </span>
                              {!isRead && notif.category === 'alert' && (
                                <button
                                  onClick={() => handleAcknowledge(notif.id)}
                                  className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold transition-colors"
                                >
                                  Mark as read
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              ) : (
                <Card className="glass-card border-white/10">
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <CheckCircle2 className="w-10 h-10 text-emerald-400 mb-3" />
                    <p className="text-sm font-medium text-white">
                      Clear Timeline
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      No notifications match your current filter parameters.
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>

          {/* Configuration Panel */}
          <div className="space-y-4 lg:col-span-1">
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardHeader className="pb-3 border-b border-white/5">
                <CardTitle className="text-sm font-semibold text-white flex items-center gap-2">
                  <Settings className="w-4 h-4 text-indigo-400" />
                  Alert Threshold Limits
                </CardTitle>
              </CardHeader>
              <CardContent className="p-5 space-y-5">
                {/* Consumption Threshold */}
                <div className="space-y-2">
                  <Label className="text-xs text-slate-300 flex items-center gap-2">
                    <Zap className="w-3.5 h-3.5 text-amber-400" />
                    High Load Limit (kW)
                  </Label>
                  <Input
                    id="threshold-input"
                    type="number"
                    step="0.1"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    className="bg-[#111827] border-white/10 text-white h-10 text-xs"
                  />
                </div>

                <Separator className="bg-white/5" />

                {/* Anomaly Sensitivity */}
                <div className="space-y-2">
                  <Label className="text-xs text-slate-300 flex items-center gap-2">
                    <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
                    Anomaly Z-Score Sensitivity
                  </Label>
                  <Select value={sensitivity} onValueChange={(v) => setSensitivity(v || 'medium')}>
                    <SelectTrigger className="bg-[#111827] border-white/10 text-white text-xs h-10">
                      <SelectValue placeholder="Select sensitivity" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#1f2937] border-white/10 text-white text-xs">
                      <SelectItem value="low">Low (Standard deviation: 3.0)</SelectItem>
                      <SelectItem value="medium">Medium (Standard deviation: 2.0)</SelectItem>
                      <SelectItem value="high">High (Standard deviation: 1.5)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  onClick={handleSaveConfig}
                  disabled={saving}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold h-9 text-xs"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Alert Rules'}
                </Button>
              </CardContent>
            </Card>

            {/* Load Shifting Recommendations Card */}
            <Card className="bg-[#111827]/80 border-white/10 backdrop-blur-md">
              <CardContent className="p-4 space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Zap className="w-4 h-4 text-emerald-400" />
                    ONEE Tariff Rates
                  </h4>
                  <p className="text-xs text-slate-400 mt-1">
                    Progressive tariffs mapped dynamically from utility standards
                  </p>
                </div>
                
                <div className="space-y-3">
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs">
                    <div className="flex justify-between font-medium text-emerald-400 mb-1">
                      <span>Social Rate (Tranche 1):</span>
                      <span>0.9010 MAD/kWh</span>
                    </div>
                    <div className="flex justify-between font-medium text-amber-400">
                      <span>Normal Rate (Tranche 2):</span>
                      <span>1.0100 MAD/kWh</span>
                    </div>
                  </div>

                  {[
                    {
                      appliance: "Washing & Drying",
                      advice: "Run cycles after 22:00 for off-peak progressive buffers.",
                    },
                    {
                      appliance: "Heating & Cooling",
                      advice: "Control AC runtime during late-afternoon peaks.",
                    },
                  ].map((rec, i) => (
                    <div key={i} className="text-xs p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <p className="font-semibold text-slate-200">{rec.appliance}</p>
                      <p className="text-slate-400 mt-0.5">{rec.advice}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
