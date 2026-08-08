'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  Cpu,
  Database,
  Edit2,
  Loader2,
  RefreshCw,
  Search,
  Shield,
  UserCheck,
  Users,
  UserX,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';

import AppLayout from '@/components/layout/app-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { adminApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import type { AccountLifecycleStatus, AdminUser, ModelReadiness, SystemHealth } from '@/types';


function Fact({ label, value, healthy }: { label: string; value: string | number; healthy?: boolean }) {
  return <div className="border-l-2 border-indigo-400/60 pl-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 flex items-center gap-2 text-lg font-semibold text-white">{healthy === undefined ? null : healthy ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <XCircle className="h-4 w-4 text-red-400" />}{value}</p></div>;
}

const LIFECYCLE_LABELS: Record<AccountLifecycleStatus, string> = {
  pending_verification: 'Pending verification',
  active: 'Active',
  disabled: 'Disabled',
};

function lifecycleStatus(entry: AdminUser): AccountLifecycleStatus {
  if (entry.lifecycle_status) return entry.lifecycle_status;
  if (!entry.email_verified_at) return 'pending_verification';
  return entry.is_active ? 'active' : 'disabled';
}

function lifecycleBadgeClass(status: AccountLifecycleStatus): string {
  if (status === 'active') return 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300';
  if (status === 'pending_verification') return 'border-amber-400/30 bg-amber-400/10 text-amber-300';
  return 'border-slate-500/30 bg-slate-500/10 text-slate-400';
}

export default function AdminPage() {
  const { user, isLoading: authLoading } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [models, setModels] = useState<ModelReadiness[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | AccountLifecycleStatus>('all');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [role, setRole] = useState<'admin' | 'user'>('user');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [nextUsers, nextHealth, nextModel] = await Promise.all([
        adminApi.getUsers(),
        adminApi.getHealth(),
        adminApi.getAllModelReadiness(),
      ]);
      setUsers(nextUsers);
      setHealth(nextHealth);
      setModels(nextModel.artifacts);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to load administration data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.role !== 'admin') return;
    void load();
    const timer = window.setInterval(() => void load(true), 30_000);
    return () => window.clearInterval(timer);
  }, [load, user?.role]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return users.filter((entry) => {
      const matchesQuery = !query || `${entry.full_name || ''} ${entry.email}`.toLowerCase().includes(query);
      const matchesStatus = statusFilter === 'all' || lifecycleStatus(entry) === statusFilter;
      return matchesQuery && matchesStatus;
    });
  }, [search, statusFilter, users]);

  const lifecycleCounts = useMemo(() => users.reduce((counts, entry) => {
    counts[lifecycleStatus(entry)] += 1;
    return counts;
  }, { active: 0, pending_verification: 0, disabled: 0 } as Record<AccountLifecycleStatus, number>), [users]);

  const openEditor = (entry: AdminUser) => {
    setEditing(entry);
    setRole(entry.role);
  };

  const saveRole = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const updated = await adminApi.updateUser(editing.id, { role });
      setUsers((current) => current.map((entry) => entry.id === updated.id ? { ...entry, ...updated } : entry));
      setEditing(null);
      toast.success('User role updated.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update this user.');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (entry: AdminUser) => {
    setSaving(true);
    try {
      const updated = await adminApi.updateUser(entry.id, { is_active: !entry.is_active });
      setUsers((current) => current.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
      if (lifecycleStatus(updated) === 'pending_verification') {
        toast.success(updated.is_active
          ? 'User enabled; email verification is still required.'
          : 'User disabled; verification remains pending.');
      } else {
        toast.success(updated.is_active ? 'User activated.' : 'User deactivated.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to update this user.');
    } finally {
      setSaving(false);
    }
  };

  if (authLoading) return <AppLayout><div className="flex min-h-[50vh] items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-indigo-400" /></div></AppLayout>;
  if (user?.role !== 'admin') return <AppLayout><div className="flex min-h-[60vh] flex-col items-center justify-center text-center"><Shield className="h-12 w-12 text-slate-600" /><h1 className="mt-4 text-xl font-semibold text-white">Access denied</h1><p className="mt-2 text-sm text-slate-400">Administrator access is required.</p></div></AppLayout>;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex items-center justify-between gap-3"><div><h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Shield className="h-6 w-6 text-indigo-400" />Administration</h1><p className="mt-1 text-sm text-slate-400">User access and read-only release readiness</p></div><Button variant="outline" size="icon" onClick={() => void load()} disabled={loading} title="Refresh administration data" aria-label="Refresh administration data"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></Button></header>

        <section className="grid gap-5 border-y border-white/10 bg-white/[0.025] px-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="Total users" value={health?.total_users ?? users.length} />
          <Fact label="Active users" value={health?.active_users ?? lifecycleCounts.active} />
          <Fact label="Pending verification" value={health?.pending_users ?? lifecycleCounts.pending_verification} />
          <Fact label="Disabled users" value={health?.disabled_users ?? lifecycleCounts.disabled} />
          <Fact label="Product forecasts" value={health?.total_forecasts ?? 0} />
          <Fact label="Database" value={health?.database_status || 'Unknown'} healthy={health?.database_status === 'healthy'} />
          <Fact label="Forecast runtime" value={health?.forecast_status || 'Unknown'} healthy={health?.forecast_status === 'ready'} />
          <Fact label="Process" value={health?.status || 'Unknown'} healthy={health?.status === 'operational'} />
        </section>

        <Tabs defaultValue="users">
          <TabsList><TabsTrigger value="users"><Users className="h-4 w-4" />Users</TabsTrigger><TabsTrigger value="system"><Activity className="h-4 w-4" />System</TabsTrigger></TabsList>
          <TabsContent value="users" className="mt-5 space-y-4">
            <div className="flex max-w-2xl flex-col gap-3 sm:flex-row">
              <div className="relative flex-1"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search users" className="pl-9" /></div>
              <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as 'all' | AccountLifecycleStatus)}>
                <SelectTrigger className="w-full sm:w-52" aria-label="Filter users by status"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="all">All statuses</SelectItem><SelectItem value="pending_verification">Pending verification</SelectItem><SelectItem value="active">Active</SelectItem><SelectItem value="disabled">Disabled</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="overflow-x-auto border border-white/10">
              <Table><TableHeader><TableRow><TableHead>User</TableHead><TableHead>Role</TableHead><TableHead>Status</TableHead><TableHead>Created</TableHead><TableHead className="w-24 text-right">Actions</TableHead></TableRow></TableHeader><TableBody>
                {filtered.map((entry) => {
                  const status = lifecycleStatus(entry);
                  return <TableRow key={entry.id}><TableCell><p className="font-medium text-white">{entry.full_name || 'Unnamed user'}</p><p className="text-xs text-slate-500">{entry.email}</p></TableCell><TableCell><Badge variant="outline" className="capitalize">{entry.role}</Badge></TableCell><TableCell><Badge variant="outline" className={lifecycleBadgeClass(status)}>{LIFECYCLE_LABELS[status]}</Badge></TableCell><TableCell className="text-slate-400">{new Date(entry.created_at).toLocaleDateString()}</TableCell><TableCell><div className="flex justify-end gap-1"><Button size="icon-sm" variant="ghost" onClick={() => openEditor(entry)} title="Edit role" aria-label={`Edit ${entry.email}`}><Edit2 className="h-4 w-4" /></Button><Button size="icon-sm" variant="ghost" onClick={() => void toggleActive(entry)} disabled={saving || entry.id === user.id} title={entry.is_active ? 'Disable account' : 'Enable account'} aria-label={`${entry.is_active ? 'Disable' : 'Enable'} ${entry.email}`}>{entry.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}</Button></div></TableCell></TableRow>;
                })}
                {!filtered.length && !loading ? <TableRow><TableCell colSpan={5} className="py-12 text-center text-slate-500">No users match the current search and status filter.</TableCell></TableRow> : null}
              </TableBody></Table>
            </div>
          </TabsContent>
          <TabsContent value="system" className="mt-5">
            <div className="grid gap-6 border-y border-white/10 py-5 lg:grid-cols-2">
              <div><h2 className="flex items-center gap-2 text-sm font-semibold text-white"><Cpu className="h-4 w-4 text-cyan-400" />Packaged forecast artifacts</h2><div className="mt-4 space-y-5">{models.map((model) => <dl key={model.horizon_hours} className="space-y-2 border-l-2 border-white/10 pl-3 text-sm"><div><dt className="text-slate-500">Capability</dt><dd className="text-slate-200">{model.display_name} · {model.horizon_hours}h</dd></div><div><dt className="text-slate-500">State</dt><dd className={model.warmed ? 'text-emerald-300' : model.enabled ? 'text-red-300' : 'text-slate-400'}>{model.warmed ? 'Warm-up passed' : model.enabled ? 'Warm-up failed' : 'Disabled'}</dd></div><div><dt className="text-slate-500">Version / SHA-256</dt><dd className="break-all font-mono text-xs text-slate-300">{model.version} · {model.artifact_fingerprint || 'Unavailable'}</dd></div>{model.error ? <div><dt className="text-slate-500">Detail</dt><dd className={model.enabled ? 'text-red-300' : 'text-slate-400'}>{model.error}</dd></div> : null}</dl>)}</div></div>
              <div><h2 className="flex items-center gap-2 text-sm font-semibold text-white"><Database className="h-4 w-4 text-emerald-400" />Runtime</h2><dl className="mt-4 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-slate-500">CPU</dt><dd className="mt-1 text-lg text-white">{health?.cpu_usage.toFixed(1) ?? '-'}%</dd></div><div><dt className="text-slate-500">Memory</dt><dd className="mt-1 text-lg text-white">{health?.memory_usage.toFixed(1) ?? '-'}%</dd></div><div><dt className="text-slate-500">Uptime</dt><dd className="mt-1 text-lg text-white">{health ? `${Math.floor(health.uptime_seconds / 3600)}h` : '-'}</dd></div><div><dt className="text-slate-500">Database</dt><dd className="mt-1 text-lg capitalize text-white">{health?.database_status || '-'}</dd></div></dl></div>
            </div>
          </TabsContent>
        </Tabs>

        <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}><DialogContent><DialogHeader><DialogTitle>Edit user role</DialogTitle></DialogHeader><div className="space-y-4"><div><Label>User</Label><p className="mt-2 text-sm text-slate-300">{editing?.email}</p></div><div><Label htmlFor="admin-role">Role</Label><Select value={role} onValueChange={(value) => setRole(value as 'admin' | 'user')}><SelectTrigger id="admin-role" className="mt-2"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="user">User</SelectItem><SelectItem value="admin">Admin</SelectItem></SelectContent></Select></div><Button onClick={() => void saveRole()} disabled={saving} className="w-full">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Save role</Button></div></DialogContent></Dialog>
      </div>
    </AppLayout>
  );
}
