'use client';

import React, { useState, useEffect } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Shield,
  Users,
  Cpu,
  Activity,
  Search,
  Edit2,
  MoreHorizontal,
  UserCheck,
  UserX,
  Server,
  Database,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { adminApi, API_BASE_URL } from '@/lib/api';
import { parseDate } from '@/lib/utils';
import { AdminUser, SystemHealth, ModelRegistry } from '@/types';
import { toast } from 'sonner';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';



// Fallback demo data in case of error
const demoSystemHealth = {
  status: 'healthy',
  uptime_seconds: 3900000,
  cpu_usage: 23,
  memory_usage: 48,
  active_users: 0,
  requests_today: 0,
};

const isOnline = (lastActivity: string | undefined | null) => {
  if (!lastActivity) return false;
  try {
    const activityDate = parseDate(lastActivity);
    // Since backend activity updates are throttled to 10s, and frontend navbar alerts poll
    // every 10s, active tabs will have a last_activity update within 20s.
    // Set threshold to 25 seconds for highly responsive offline detection.
    return Date.now() - activityDate.getTime() < 25 * 1000;
  } catch {
    return false;
  }
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('users');
  const [searchQuery, setSearchQuery] = useState('');
  
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [models, setModels] = useState<ModelRegistry[]>([]);
  const [health, setHealth] = useState<SystemHealth | any>(demoSystemHealth);
  const [loading, setLoading] = useState(true);
  
  const [editUser, setEditUser] = useState<AdminUser | null>(null);
  const [editRole, setEditRole] = useState('');
  const [isSavingUser, setIsSavingUser] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  
  const [selectedModel, setSelectedModel] = useState<ModelRegistry | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  
  const { user } = useAuth();

  useEffect(() => {
    if (user?.role !== 'admin') return;
    
    const fetchData = async () => {
      try {
        const [usersData, modelsData, healthData] = await Promise.all([
          adminApi.getUsers(),
          adminApi.getModels(),
          adminApi.getHealth().catch(() => demoSystemHealth)
        ]);
        setUsers(usersData);
        setModels(modelsData);
        setHealth(healthData);
      } catch (err) {
        console.error('Failed to fetch admin data', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 5000); // Poll user list every 5s for real-time presence
    return () => clearInterval(interval);
  }, [user]);

  const filteredUsers = users.filter(
    (u) =>
      u.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSaveUser = async () => {
    if (!editUser) return;
    setIsSavingUser(true);
    try {
      const updatedUser = await adminApi.updateUser(editUser.id, {
        role: editRole as any,
      });
      setUsers(users.map(u => u.id === updatedUser.id ? { ...u, ...updatedUser } : u));
      setIsDialogOpen(false);
      toast.success(`User updated successfully`);
    } catch (err) {
      console.error('Failed to update user', err);
      toast.error('Failed to update user');
    } finally {
      setIsSavingUser(false);
    }
  };

  const handleToggleStatus = async () => {
    if (!editUser) return;
    setIsSavingUser(true);
    try {
      const updatedUser = await adminApi.updateUser(editUser.id, {
        is_active: !editUser.is_active,
      });
      setUsers(users.map(u => u.id === updatedUser.id ? { ...u, ...updatedUser } : u));
      setEditUser({ ...editUser, ...updatedUser });
      toast.success(updatedUser.is_active ? 'User activated' : 'User deactivated');
    } catch (err) {
      console.error('Failed to update status', err);
      toast.error('Failed to update user status');
    } finally {
      setIsSavingUser(false);
    }
  };

  const handleRetrainModel = async (modelName: string, displayName: string) => {
    // 1. Instantly transition status locally to 'training' for immediate UI feedback
    setModels(prev => prev.map(m => m.name === modelName ? { ...m, status: 'training' } : m));
    
    try {
      await adminApi.retrainModel(modelName);
      toast.success(`Simulating model retraining for ${displayName}. Keep polling state...`);
    } catch (err) {
      console.error('Failed to trigger retraining', err);
      toast.error(`Failed to trigger retraining for ${displayName}`);
      // Revert status on failure
      setModels(prev => prev.map(m => m.name === modelName ? { ...m, status: 'active' } : m));
    }
  };

  function formatUptime(seconds: number): string {
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    if (d > 0) return `${d}d ${h}h`;
    return `${h}h`;
  }

  // Admin guard
  if (user && user.role !== 'admin') {
    return (
      <AppLayout>
        <div className="flex flex-col items-center justify-center h-[60vh]">
          <Shield className="w-16 h-16 text-slate-600 mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">
            Access Denied
          </h2>
          <p className="text-sm text-slate-400">
            You need admin privileges to access this page.
          </p>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="w-6 h-6 text-blue-400" />
            Admin Panel
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Manage users, models, and system settings
          </p>
        </div>

        {/* System Health Overview */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: 'System Status',
              value: health.status,
              icon: Activity,
              iconBg: 'bg-emerald-500/10',
              iconText: 'text-emerald-400',
            },
            {
              label: 'Uptime',
              value: formatUptime(health.uptime_seconds || 0),
              icon: Clock,
              iconBg: 'bg-blue-500/10',
              iconText: 'text-blue-400',
            },
            {
              label: 'Active Users',
              value: users.filter(u => isOnline(u.last_activity)).length.toString(),
              icon: Users,
              iconBg: 'bg-cyan-500/10',
              iconText: 'text-cyan-400',
            },
            {
              label: 'Database Status',
              value: health.database_status || 'healthy',
              icon: Server,
              iconBg: 'bg-violet-500/10',
              iconText: 'text-violet-400',
            },
          ].map((stat) => (
            <Card
              key={stat.label}
              className="glass-card border-white/[0.06] stat-card"
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center ${stat.iconBg}`}
                  >
                    <stat.icon
                      className={`w-4 h-4 ${stat.iconText}`}
                    />
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">{stat.label}</p>
                    <p className="text-sm font-semibold text-white capitalize">
                      {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : stat.value}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Resource Bars */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            { label: 'CPU Usage', value: Math.round(health?.cpu_usage ?? 0), color: '#3B82F6' },
            {
              label: 'Memory Usage',
              value: Math.round(health?.memory_usage ?? 0),
              color: '#06B6D4',
            },
          ].map((resource) => (
            <Card
              key={resource.label}
              className="glass-card border-white/[0.06]"
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-400">
                    {resource.label}
                  </span>
                  <span className="text-xs font-medium text-white">
                    {resource.value}%
                  </span>
                </div>
                <div className="h-2 rounded-full bg-white/[0.04] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000"
                    style={{
                      width: `${resource.value}%`,
                      background: `linear-gradient(90deg, ${resource.color}60, ${resource.color})`,
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white/[0.04] border border-white/[0.06] p-1">
            <TabsTrigger
              id="admin-tab-users"
              value="users"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400"
            >
              <Users className="w-4 h-4 mr-2" />
              Users
            </TabsTrigger>
            <TabsTrigger
              id="admin-tab-models"
              value="models"
              className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400 text-slate-400"
            >
              <Cpu className="w-4 h-4 mr-2" />
              Model Registry
            </TabsTrigger>
          </TabsList>

          {/* Users Tab */}
          <TabsContent value="users" className="space-y-4 mt-4">
            {/* Search */}
            <div className="flex items-center gap-3">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <Input
                  id="admin-search-users"
                  placeholder="Search users..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/[0.04] border-white/[0.08] text-white placeholder:text-slate-500 h-10"
                />
              </div>
              <Badge className="bg-white/[0.04] text-slate-400 border-white/[0.06]">
                {filteredUsers.length} users
              </Badge>
            </div>

            {/* Users Table */}
            <Card className="glass-card border-white/[0.06] overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="border-white/[0.06] hover:bg-transparent">
                    <TableHead className="text-slate-400 font-medium">
                      User
                    </TableHead>
                    <TableHead className="text-slate-400 font-medium">
                      Role
                    </TableHead>
                    <TableHead className="text-slate-400 font-medium">
                      Status
                    </TableHead>
                    <TableHead className="text-slate-400 font-medium">
                      Created At
                    </TableHead>
                    <TableHead className="text-slate-400 font-medium text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={5} className="h-24 text-center">
                        <Loader2 className="w-6 h-6 animate-spin text-slate-500 mx-auto" />
                      </TableCell>
                    </TableRow>
                  ) : filteredUsers.map((u) => (
                    <TableRow
                      key={u.id}
                      className="border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                    >
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="w-8 h-8">
                            {u.avatar_url && (
                              <AvatarImage
                                src={u.avatar_url.startsWith('http') ? u.avatar_url : `${API_BASE_URL}${u.avatar_url}`}
                                alt={u.full_name}
                                className="object-cover"
                              />
                            )}
                            <AvatarFallback className="bg-gradient-to-br from-blue-500 to-cyan-500 text-white text-xs font-semibold">
                              {u.full_name
                                .split(' ')
                                .map((n) => n[0])
                                .join('')
                                .toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <p className="text-sm font-medium text-white">
                              {u.full_name}
                            </p>
                            <p className="text-xs text-slate-500">{u.email}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[10px] uppercase ${
                            u.role === 'admin'
                              ? 'border-purple-500/20 text-purple-400 bg-purple-500/10'
                              : 'border-slate-500/20 text-slate-400 bg-slate-500/10'
                          }`}
                        >
                          {u.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          {isOnline(u.last_activity) ? (
                            <>
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                              <span className="text-xs text-emerald-400">
                                Online
                              </span>
                            </>
                          ) : (
                            <>
                              <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                              <span className="text-xs text-slate-500">
                                Offline
                              </span>
                            </>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-slate-400">
                        {parseDate(u.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Dialog open={isDialogOpen && editUser?.id === u.id} onOpenChange={(open) => {
                          if (!open) setIsDialogOpen(false);
                          else {
                            setEditUser(u);
                            setEditRole(u.role);
                            setIsDialogOpen(true);
                          }
                        }}>
                          <DialogTrigger
                            render={
                              <Button
                                id={`edit-user-${u.id}`}
                                variant="ghost"
                                size="sm"
                                className="text-slate-400 hover:text-white hover:bg-white/[0.06]"
                              />
                            }
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </DialogTrigger>
                          <DialogContent className="bg-[#111827] border-white/10 text-white">
                            <DialogHeader>
                              <DialogTitle>Edit User</DialogTitle>
                            </DialogHeader>
                            {editUser && (
                              <div className="space-y-4 mt-2">
                                <div>
                                  <Label className="text-xs text-slate-300">
                                    Name
                                  </Label>
                                  <p className="text-sm text-white mt-1">
                                    {editUser.full_name}
                                  </p>
                                </div>
                                <div>
                                  <Label className="text-xs text-slate-300">
                                    Email
                                  </Label>
                                  <p className="text-sm text-white mt-1">
                                    {editUser.email}
                                  </p>
                                </div>
                                <div className="space-y-2">
                                  <Label className="text-xs text-slate-300">
                                    Role
                                  </Label>
                                  <Select
                                    value={editRole}
                                    onValueChange={(v) => setEditRole(v ?? '')}
                                  >
                                    <SelectTrigger className="bg-white/[0.04] border-white/[0.08] text-white">
                                      <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#111827] border-white/10">
                                      <SelectItem value="user" className="text-slate-300">User</SelectItem>
                                      <SelectItem
                                        value="admin"
                                        className="text-slate-300"
                                      >
                                        Admin
                                      </SelectItem>
                                    </SelectContent>
                                  </Select>
                                </div>
                                <div className="flex gap-2 pt-2">
                                  <Button
                                    id="save-user-btn"
                                    className="flex-1 bg-blue-600 hover:bg-blue-500"
                                    onClick={handleSaveUser}
                                    disabled={isSavingUser}
                                  >
                                    {isSavingUser ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                                    Save Changes
                                  </Button>
                                  <Button
                                    id="toggle-status-btn"
                                    variant="outline"
                                    onClick={handleToggleStatus}
                                    disabled={isSavingUser}
                                    className={`border-white/[0.08] ${
                                      editUser.is_active
                                        ? 'text-red-400 hover:bg-red-500/10'
                                        : 'text-emerald-400 hover:bg-emerald-500/10'
                                    }`}
                                  >
                                    {editUser.is_active ? (
                                      <>
                                        <UserX className="w-4 h-4 mr-1" />{' '}
                                        Deactivate
                                      </>
                                    ) : (
                                      <>
                                        <UserCheck className="w-4 h-4 mr-1" />{' '}
                                        Activate
                                      </>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            )}
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          </TabsContent>

          {/* Models Tab */}
          <TabsContent value="models" className="space-y-4 mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {loading ? (
                <div className="col-span-2 py-12 flex justify-center">
                  <Loader2 className="w-8 h-8 animate-spin text-slate-500" />
                </div>
              ) : models.map((model) => (
                <Card
                  key={model.id || model.name}
                  id={`model-card-${model.id || model.name}`}
                  className="glass-card border-white/[0.06] hover:border-white/[0.1] transition-all duration-200"
                >
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                          <Cpu className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-white">
                            {(model as any).display_name || model.name}
                          </h3>
                          <p className="text-xs text-slate-500">
                            v{model.version || '1.0.0'}
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[10px] uppercase ${
                          model.status === 'active' || (model as any).is_active || model.status === undefined
                            ? 'border-emerald-500/20 text-emerald-400 bg-emerald-500/10'
                            : model.status === 'training'
                            ? 'border-amber-500/20 text-amber-400 bg-amber-500/10'
                            : 'border-slate-500/20 text-slate-500 bg-slate-500/10'
                        }`}
                      >
                        {(model.status === 'active' || (model as any).is_active || model.status === undefined) && (
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                        )}
                        {model.status === 'training' && (
                          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        )}
                        {model.status === 'inactive' && (
                          <XCircle className="w-3 h-3 mr-1" />
                        )}
                        {model.status || ((model as any).is_active ? 'active' : 'inactive')}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="p-2 rounded-lg bg-white/[0.02]">
                        <p className="text-[10px] text-slate-500 uppercase">
                          R² Score
                        </p>
                        <p className="text-sm font-semibold text-emerald-400">
                          {(model as any).training_metrics?.r2_score ? (model as any).training_metrics.r2_score.toFixed(4) : (model.accuracy ? `${model.accuracy}%` : 'N/A')}
                        </p>
                      </div>
                      <div className="p-2 rounded-lg bg-white/[0.02]">
                        <p className="text-[10px] text-slate-500 uppercase">
                          Params
                        </p>
                        <p className="text-sm font-semibold text-white">
                          {(model as any).parameters ? 'Custom' : 'Default'}
                        </p>
                      </div>
                      <div className="p-2 rounded-lg bg-white/[0.02]">
                        <p className="text-[10px] text-slate-500 uppercase">
                          Type
                        </p>
                        <p className="text-sm font-semibold text-slate-300 truncate">
                          {(model as any).architecture_type || 'Unknown'}
                        </p>
                      </div>
                    </div>

                    <div className="flex gap-2 mt-4">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRetrainModel(model.name, (model as any).display_name || model.name)}
                        disabled={model.status === 'training'}
                        className="flex-1 border-white/[0.08] text-slate-300 hover:text-white hover:bg-white/[0.04] text-xs"
                      >
                        {model.status === 'training' ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin text-amber-400" />
                            Training...
                          </>
                        ) : (
                          <>
                            <Database className="w-3 h-3 mr-1" />
                            Retrain
                          </>
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedModel(model);
                          setIsDetailsOpen(true);
                        }}
                        className="flex-1 border-white/[0.08] text-slate-300 hover:text-white hover:bg-white/[0.04] text-xs"
                      >
                        <MoreHorizontal className="w-3 h-3 mr-1" />
                        Details
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Model Details Dialog */}
      <Dialog open={isDetailsOpen} onOpenChange={setIsDetailsOpen}>
        <DialogContent className="bg-[#111827] border-white/10 text-white max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-white">
              <Cpu className="w-5 h-5 text-blue-400" />
              {selectedModel ? (selectedModel as any).display_name || selectedModel.name : 'Model Details'}
            </DialogTitle>
          </DialogHeader>
          {selectedModel && (
            <div className="space-y-4 mt-2">
              <div>
                <Label className="text-xs text-slate-400">Description</Label>
                <p className="text-sm text-slate-200 mt-1">
                  {(selectedModel as any).description || 'No description available.'}
                </p>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs text-slate-400">Version</Label>
                  <p className="text-sm text-white mt-0.5">{selectedModel.version || '1.0.0'}</p>
                </div>
                <div>
                  <Label className="text-xs text-slate-400">Architecture Type</Label>
                  <p className="text-sm text-white capitalize mt-0.5">
                    {(selectedModel as any).architecture_type || 'Unknown'}
                  </p>
                </div>
                <div>
                  <Label className="text-xs text-slate-400">R² Score</Label>
                  <p className="text-sm text-emerald-400 font-semibold mt-0.5">
                    {(selectedModel as any).training_metrics?.r2_score ? (selectedModel as any).training_metrics.r2_score.toFixed(4) : (selectedModel.accuracy ? `${selectedModel.accuracy}%` : 'N/A')}
                  </p>
                </div>
                <div>
                  <Label className="text-xs text-slate-400">Last Trained</Label>
                  <p className="text-sm text-white mt-0.5">
                    {selectedModel.last_trained ? new Date(selectedModel.last_trained).toLocaleString() : 'N/A'}
                  </p>
                </div>
              </div>

              {(selectedModel as any).training_metrics && (
                <div>
                  <Label className="text-xs text-slate-400 block mb-2">Training Metrics</Label>
                  <div className="grid grid-cols-4 gap-2">
                    <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <p className="text-[10px] text-slate-500 uppercase">MAE</p>
                      <p className="text-sm font-medium text-white">{(selectedModel as any).training_metrics.mae}</p>
                    </div>
                    <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <p className="text-[10px] text-slate-500 uppercase">RMSE</p>
                      <p className="text-sm font-medium text-white">{(selectedModel as any).training_metrics.rmse}</p>
                    </div>
                    <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <p className="text-[10px] text-slate-500 uppercase">MAPE</p>
                      <p className="text-sm font-medium text-white">{(selectedModel as any).training_metrics.mape}%</p>
                    </div>
                    <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <p className="text-[10px] text-slate-500 uppercase">R² Score</p>
                      <p className="text-sm font-medium text-blue-400">{(selectedModel as any).training_metrics.r2_score}</p>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <Label className="text-xs text-slate-400 block mb-2">Model Hyperparameters</Label>
                <div className="border border-white/10 rounded-lg overflow-hidden bg-white/[0.02] max-h-60 overflow-y-auto">
                  <Table>
                    <TableHeader className="bg-white/[0.04]">
                      <TableRow className="border-white/10 hover:bg-transparent">
                        <TableHead className="text-xs text-slate-400 h-8 py-1 font-medium">Hyperparameter</TableHead>
                        <TableHead className="text-xs text-slate-400 h-8 py-1 font-medium text-right">Value</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedModel.parameters && Object.entries(selectedModel.parameters).map(([key, val]) => (
                        <TableRow key={key} className="border-white/[0.04] hover:bg-white/[0.01]">
                          <TableCell className="text-xs text-slate-300 py-1.5 capitalize">
                            {key.replace(/_/g, ' ')}
                          </TableCell>
                          <TableCell className="text-xs text-white text-right py-1.5 font-mono">
                            {String(val)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
