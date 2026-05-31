'use client';

import React, { useState } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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

// Demo data
const demoUsers = [
  {
    id: '1',
    full_name: 'Dr. Sarah Chen',
    email: 'sarah.chen@university.edu',
    role: 'admin',
    is_active: true,
    forecast_count: 89,
    last_login: '2 minutes ago',
    created_at: '2024-01-15',
  },
  {
    id: '2',
    full_name: 'Ahmed Benali',
    email: 'a.benali@company.com',
    role: 'user',
    is_active: true,
    forecast_count: 45,
    last_login: '1 hour ago',
    created_at: '2024-03-22',
  },
  {
    id: '3',
    full_name: 'Maria Garcia',
    email: 'maria.g@research.org',
    role: 'user',
    is_active: true,
    forecast_count: 32,
    last_login: '3 hours ago',
    created_at: '2024-06-10',
  },
  {
    id: '4',
    full_name: 'James Wilson',
    email: 'j.wilson@energy.io',
    role: 'user',
    is_active: false,
    forecast_count: 12,
    last_login: '5 days ago',
    created_at: '2024-08-05',
  },
  {
    id: '5',
    full_name: 'Fatima Zahra',
    email: 'f.zahra@lab.edu',
    role: 'user',
    is_active: true,
    forecast_count: 67,
    last_login: '30 minutes ago',
    created_at: '2024-02-18',
  },
];

const demoModels = [
  {
    id: '1',
    name: 'CNN-BiLSTM',
    version: '2.1.0',
    status: 'active',
    accuracy: 96.2,
    last_trained: '2 days ago',
    parameters: '2.4M',
  },
  {
    id: '2',
    name: 'SOTA Hybrid',
    version: '1.3.2',
    status: 'active',
    accuracy: 95.8,
    last_trained: '5 days ago',
    parameters: '3.1M',
  },
  {
    id: '3',
    name: 'PatchTST',
    version: '3.0.1',
    status: 'active',
    accuracy: 97.1,
    last_trained: '1 day ago',
    parameters: '1.8M',
  },
  {
    id: '4',
    name: 'LSTM Baseline',
    version: '1.0.0',
    status: 'inactive',
    accuracy: 91.3,
    last_trained: '30 days ago',
    parameters: '0.8M',
  },
];

const systemHealth = {
  status: 'healthy',
  uptime: '45 days, 12 hours',
  cpu: 23,
  memory: 48,
  activeUsers: 12,
  requestsToday: 1847,
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('users');
  const [searchQuery, setSearchQuery] = useState('');
  const [editUser, setEditUser] = useState<typeof demoUsers[0] | null>(null);
  const [editRole, setEditRole] = useState('');
  const { user } = useAuth();

  const filteredUsers = demoUsers.filter(
    (u) =>
      u.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
              value: systemHealth.status,
              icon: Activity,
              color: 'emerald',
            },
            {
              label: 'Uptime',
              value: systemHealth.uptime,
              icon: Clock,
              color: 'blue',
            },
            {
              label: 'Active Users',
              value: systemHealth.activeUsers.toString(),
              icon: Users,
              color: 'cyan',
            },
            {
              label: 'Requests Today',
              value: systemHealth.requestsToday.toLocaleString(),
              icon: Server,
              color: 'violet',
            },
          ].map((stat) => (
            <Card
              key={stat.label}
              className="glass-card border-white/[0.06] stat-card"
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center bg-${stat.color}-500/10`}
                  >
                    <stat.icon
                      className={`w-4 h-4 text-${stat.color}-400`}
                    />
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">{stat.label}</p>
                    <p className="text-sm font-semibold text-white capitalize">
                      {stat.value}
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
            { label: 'CPU Usage', value: systemHealth.cpu, color: '#3B82F6' },
            {
              label: 'Memory Usage',
              value: systemHealth.memory,
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
                      Forecasts
                    </TableHead>
                    <TableHead className="text-slate-400 font-medium">
                      Last Login
                    </TableHead>
                    <TableHead className="text-slate-400 font-medium text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((u) => (
                    <TableRow
                      key={u.id}
                      className="border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                    >
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-xs font-semibold">
                            {u.full_name
                              .split(' ')
                              .map((n) => n[0])
                              .join('')}
                          </div>
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
                          {u.is_active ? (
                            <>
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                              <span className="text-xs text-emerald-400">
                                Active
                              </span>
                            </>
                          ) : (
                            <>
                              <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                              <span className="text-xs text-slate-500">
                                Inactive
                              </span>
                            </>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-slate-300">
                        {u.forecast_count}
                      </TableCell>
                      <TableCell className="text-sm text-slate-400">
                        {u.last_login}
                      </TableCell>
                      <TableCell className="text-right">
                        <Dialog>
                          <DialogTrigger
                            render={
                              <Button
                                id={`edit-user-${u.id}`}
                                variant="ghost"
                                size="sm"
                                className="text-slate-400 hover:text-white hover:bg-white/[0.06]"
                              />
                            }
                            onClick={() => {
                              setEditUser(u);
                              setEditRole(u.role);
                            }}
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
                                      <SelectItem
                                        value="user"
                                        className="text-slate-300"
                                      >
                                        User
                                      </SelectItem>
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
                                  >
                                    Save Changes
                                  </Button>
                                  <Button
                                    id="toggle-status-btn"
                                    variant="outline"
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
              {demoModels.map((model) => (
                <Card
                  key={model.id}
                  id={`model-card-${model.id}`}
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
                            {model.name}
                          </h3>
                          <p className="text-xs text-slate-500">
                            v{model.version}
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[10px] uppercase ${
                          model.status === 'active'
                            ? 'border-emerald-500/20 text-emerald-400 bg-emerald-500/10'
                            : model.status === 'training'
                            ? 'border-amber-500/20 text-amber-400 bg-amber-500/10'
                            : 'border-slate-500/20 text-slate-500 bg-slate-500/10'
                        }`}
                      >
                        {model.status === 'active' && (
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                        )}
                        {model.status === 'training' && (
                          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        )}
                        {model.status === 'inactive' && (
                          <XCircle className="w-3 h-3 mr-1" />
                        )}
                        {model.status}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="p-2 rounded-lg bg-white/[0.02]">
                        <p className="text-[10px] text-slate-500 uppercase">
                          Accuracy
                        </p>
                        <p className="text-sm font-semibold text-emerald-400">
                          {model.accuracy}%
                        </p>
                      </div>
                      <div className="p-2 rounded-lg bg-white/[0.02]">
                        <p className="text-[10px] text-slate-500 uppercase">
                          Params
                        </p>
                        <p className="text-sm font-semibold text-white">
                          {model.parameters}
                        </p>
                      </div>
                      <div className="p-2 rounded-lg bg-white/[0.02]">
                        <p className="text-[10px] text-slate-500 uppercase">
                          Trained
                        </p>
                        <p className="text-sm font-semibold text-slate-300">
                          {model.last_trained}
                        </p>
                      </div>
                    </div>

                    <div className="flex gap-2 mt-4">
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1 border-white/[0.08] text-slate-300 hover:text-white hover:bg-white/[0.04] text-xs"
                      >
                        <Database className="w-3 h-3 mr-1" />
                        Retrain
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
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
    </AppLayout>
  );
}
