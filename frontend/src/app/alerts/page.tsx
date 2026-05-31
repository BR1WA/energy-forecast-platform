'use client';

import React, { useState } from 'react';
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
  AlertCircle,
  Info,
  CheckCircle2,
  Settings,
  Filter,
  Zap,
  TrendingUp,
  ShieldAlert,
  Save,
} from 'lucide-react';

// Demo alerts
const demoAlerts = [
  {
    id: '1',
    type: 'high_consumption',
    severity: 'high' as const,
    title: 'High Energy Consumption Detected',
    message:
      'Energy consumption exceeded 5000 Wh threshold at 18:00. Current reading: 5,340 Wh.',
    is_read: false,
    created_at: '10 minutes ago',
  },
  {
    id: '2',
    type: 'anomaly',
    severity: 'critical' as const,
    title: 'Anomalous Pattern Detected',
    message:
      'Unusual spike in consumption detected between 02:00-04:00. Pattern deviates 45% from baseline.',
    is_read: false,
    created_at: '1 hour ago',
  },
  {
    id: '3',
    type: 'threshold',
    severity: 'medium' as const,
    title: 'Approaching Daily Limit',
    message:
      'Daily consumption is at 85% of your configured threshold. Estimated to exceed by 20:00.',
    is_read: false,
    created_at: '3 hours ago',
  },
  {
    id: '4',
    type: 'system',
    severity: 'low' as const,
    title: 'Model Training Complete',
    message:
      'PatchTST model has completed retraining with latest data. New accuracy: 97.3%.',
    is_read: true,
    created_at: '6 hours ago',
  },
  {
    id: '5',
    type: 'high_consumption',
    severity: 'medium' as const,
    title: 'Weekly Consumption Above Average',
    message:
      'This week\'s total consumption is 12% above the 4-week rolling average.',
    is_read: true,
    created_at: '1 day ago',
  },
  {
    id: '6',
    type: 'system',
    severity: 'low' as const,
    title: 'Forecast Accuracy Improved',
    message:
      'CNN-BiLSTM model accuracy improved from 95.8% to 96.2% after latest data incorporation.',
    is_read: true,
    created_at: '2 days ago',
  },
];

const severityConfig = {
  critical: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    icon: ShieldAlert,
    badge: 'bg-red-500/10 text-red-400 border-red-500/20',
  },
  high: {
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/20',
    icon: AlertTriangle,
    badge: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  },
  medium: {
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    icon: AlertCircle,
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  },
  low: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    icon: Info,
    badge: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  },
};

export default function AlertsPage() {
  const [filter, setFilter] = useState('all');
  const [threshold, setThreshold] = useState('5000');
  const [sensitivity, setSensitivity] = useState('medium');
  const [alerts] = useState(demoAlerts);

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'all') return true;
    if (filter === 'unread') return !a.is_read;
    return a.severity === filter;
  });

  const unreadCount = alerts.filter((a) => !a.is_read).length;

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Bell className="w-6 h-6 text-blue-400" />
              Alerts
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Monitor and configure energy alerts and thresholds
            </p>
          </div>
          <Badge
            className={`${
              unreadCount > 0
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/20'
                : 'bg-white/[0.04] text-slate-400 border-white/[0.06]'
            }`}
          >
            {unreadCount} unread
          </Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Alerts List */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filter Bar */}
            <Card className="glass-card border-white/[0.06]">
              <CardContent className="p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <Filter className="w-4 h-4 text-slate-500" />
                  {['all', 'unread', 'critical', 'high', 'medium', 'low'].map(
                    (f) => (
                      <button
                        key={f}
                        id={`filter-${f}`}
                        onClick={() => setFilter(f)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 capitalize ${
                          filter === f
                            ? 'bg-blue-500/20 text-blue-400'
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

            {/* Alert Items */}
            <div className="space-y-3">
              {filteredAlerts.map((alert) => {
                const config = severityConfig[alert.severity];
                const Icon = config.icon;
                return (
                  <Card
                    key={alert.id}
                    id={`alert-${alert.id}`}
                    className={`glass-card border-white/[0.06] transition-all duration-200 hover:border-white/[0.1] ${
                      !alert.is_read ? 'ring-1 ring-blue-500/10' : ''
                    }`}
                  >
                    <CardContent className="p-4">
                      <div className="flex gap-3">
                        <div
                          className={`flex items-center justify-center w-10 h-10 rounded-xl ${config.bg} shrink-0`}
                        >
                          <Icon className={`w-5 h-5 ${config.color}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="text-sm font-semibold text-white">
                                  {alert.title}
                                </h3>
                                {!alert.is_read && (
                                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                                )}
                              </div>
                              <p className="text-sm text-slate-400 mt-1">
                                {alert.message}
                              </p>
                            </div>
                            <Badge
                              variant="outline"
                              className={`${config.badge} text-[10px] uppercase shrink-0`}
                            >
                              {alert.severity}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 mt-3">
                            <span className="text-xs text-slate-500">
                              {alert.created_at}
                            </span>
                            {!alert.is_read && (
                              <button className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                                Mark as read
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}

              {filteredAlerts.length === 0 && (
                <Card className="glass-card border-white/[0.06]">
                  <CardContent className="flex flex-col items-center justify-center py-12">
                    <CheckCircle2 className="w-10 h-10 text-emerald-400 mb-3" />
                    <p className="text-sm font-medium text-white">
                      No alerts found
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      All clear! No alerts match your filter.
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>

          {/* Configuration Panel */}
          <div className="space-y-4">
            <Card className="glass-card border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-white flex items-center gap-2">
                  <Settings className="w-4 h-4 text-blue-400" />
                  Alert Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {/* Consumption Threshold */}
                <div className="space-y-2">
                  <Label className="text-xs text-slate-300 flex items-center gap-2">
                    <Zap className="w-3 h-3 text-amber-400" />
                    High Consumption Threshold (Wh)
                  </Label>
                  <Input
                    id="threshold-input"
                    type="number"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    className="bg-white/[0.04] border-white/[0.08] text-white h-10"
                  />
                </div>

                <Separator className="bg-white/[0.06]" />

                {/* Anomaly Sensitivity */}
                <div className="space-y-2">
                  <Label className="text-xs text-slate-300 flex items-center gap-2">
                    <TrendingUp className="w-3 h-3 text-cyan-400" />
                    Anomaly Detection Sensitivity
                  </Label>
                  <Select value={sensitivity} onValueChange={(v) => setSensitivity(v ?? 'medium')}>
                    <SelectTrigger
                      id="sensitivity-select"
                      className="bg-white/[0.04] border-white/[0.08] text-white"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#111827] border-white/10">
                      <SelectItem
                        value="low"
                        className="text-slate-300 focus:text-white focus:bg-white/[0.06]"
                      >
                        Low — Fewer alerts
                      </SelectItem>
                      <SelectItem
                        value="medium"
                        className="text-slate-300 focus:text-white focus:bg-white/[0.06]"
                      >
                        Medium — Balanced
                      </SelectItem>
                      <SelectItem
                        value="high"
                        className="text-slate-300 focus:text-white focus:bg-white/[0.06]"
                      >
                        High — More sensitive
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Separator className="bg-white/[0.06]" />

                {/* Notification Preferences */}
                <div className="space-y-3">
                  <Label className="text-xs text-slate-300">
                    Notifications
                  </Label>
                  {[
                    { label: 'Email Notifications', id: 'notif-email' },
                    { label: 'Push Notifications', id: 'notif-push' },
                  ].map((n) => (
                    <label
                      key={n.id}
                      htmlFor={n.id}
                      className="flex items-center justify-between p-2 rounded-lg hover:bg-white/[0.02] cursor-pointer"
                    >
                      <span className="text-sm text-slate-300">{n.label}</span>
                      <input
                        id={n.id}
                        type="checkbox"
                        defaultChecked
                        className="w-4 h-4 rounded border-white/20 bg-white/[0.04] text-blue-500 focus:ring-blue-500/20"
                      />
                    </label>
                  ))}
                </div>

                <Button
                  id="save-alert-config"
                  className="w-full bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save Configuration
                </Button>
              </CardContent>
            </Card>

            {/* Alert Stats */}
            <Card className="glass-card border-white/[0.06]">
              <CardContent className="p-4 space-y-3">
                <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Alert Summary
                </h4>
                {Object.entries(severityConfig).map(([key, config]) => {
                  const count = alerts.filter(
                    (a) => a.severity === key
                  ).length;
                  const Icon = config.icon;
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <Icon className={`w-4 h-4 ${config.color}`} />
                        <span className="text-sm text-slate-300 capitalize">
                          {key}
                        </span>
                      </div>
                      <span className="text-sm font-medium text-white">
                        {count}
                      </span>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
