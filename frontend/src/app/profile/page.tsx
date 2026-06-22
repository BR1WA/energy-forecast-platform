'use client';

import React, { useState, useEffect, useRef } from 'react';
import AppLayout from '@/components/layout/app-layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth';
import { authApi, analyticsApi, API_BASE_URL } from '@/lib/api';
import { toast } from 'sonner';
import {
  User as UserIcon,
  Mail,
  Shield,
  Upload,
  Camera,
  AlertCircle,
  Calendar,
  Cpu,
  BarChart3,
  BarChart3 as BarChartIcon, // If needed, keeping style
  Loader2,
  Trash2,
  Clock,
  CreditCard,
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { parseDate } from '@/lib/utils';

interface UserStats {
  totalForecasts: number;
  activeAlerts: number;
  avgPeakPower: number | null;
}

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Profile forms
  const [fullName, setFullName] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Avatar states
  const [isUploading, setIsUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Stats states
  const [stats, setStats] = useState<UserStats>({
    totalForecasts: 0,
    activeAlerts: 0,
    avgPeakPower: null,
  });
  const [loadingStats, setLoadingStats] = useState(true);

  // Initialize
  useEffect(() => {
    if (user?.full_name) {
      setFullName(user.full_name);
    }
  }, [user]);

  // Load stats
  useEffect(() => {
    analyticsApi
      .getSummary()
      .then((data: any) => {
        setStats({
          totalForecasts: data.total_forecasts || 0,
          activeAlerts: data.unacknowledged_alerts || 0,
          avgPeakPower: data.avg_peak_power || null,
        });
      })
      .catch((err) => {
        console.error('Failed to load profile stats:', err);
      })
      .finally(() => setLoadingStats(false));
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      toast.error('Name cannot be empty');
      return;
    }
    setIsSavingProfile(true);
    try {
      await authApi.updateProfile({ full_name: fullName.trim() });
      toast.success('Profile updated successfully');
      await refreshUser(); // Update client auth context
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update profile');
    } finally {
      setIsSavingProfile(false);
    }
  };

  // Avatar file validation (Frontend side)
  const validateAndUploadFile = async (file: File) => {
    const allowedExtensions = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
    const maxFileSize = 2 * 1024 * 1024; // 2MB

    if (!allowedExtensions.includes(file.type.toLowerCase())) {
      toast.error('Only JPG, JPEG, PNG, GIF, and WebP images are allowed.');
      return;
    }

    if (file.size > maxFileSize) {
      toast.error('Image file size must not exceed 2MB.');
      return;
    }

    setIsUploading(true);
    setUploadProgress(20);
    
    try {
      setUploadProgress(50);
      await authApi.uploadAvatar(file);
      setUploadProgress(90);
      toast.success('Profile picture updated successfully');
      await refreshUser(); // Refresh auth user state in context
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to upload profile picture');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDeleteAvatar = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to remove your profile picture?')) {
      setIsUploading(true);
      try {
        await authApi.deleteAvatar();
        toast.success('Profile picture removed');
        await refreshUser();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to remove profile picture');
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndUploadFile(e.target.files[0]);
    }
  };

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndUploadFile(e.dataTransfer.files[0]);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase() || 'U';

  const avatarUrl = user?.avatar_url 
    ? (user.avatar_url.startsWith('http') ? user.avatar_url : `${API_BASE_URL}${user.avatar_url}`)
    : '';

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Your Profile</h1>
          <p className="text-slate-400 mt-1">
            Manage your personal profile information, upload avatar, and monitor account metrics.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Avatar & Overview */}
          <div className="space-y-6 lg:col-span-1">
            <Card className="bg-[#111827]/50 border-white/[0.06] overflow-hidden">
              <CardContent className="pt-8 pb-6 flex flex-col items-center">
                {/* Avatar Display */}
                <div 
                  className={`relative group cursor-pointer w-32 h-32 rounded-full overflow-hidden transition-all duration-300 ring-4 ${
                    dragActive ? 'ring-blue-500 scale-105' : 'ring-blue-500/20 hover:ring-blue-500/50'
                  }`}
                  onClick={triggerFileInput}
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                >
                  <Avatar className="w-full h-full rounded-none">
                    {avatarUrl ? (
                      <AvatarImage src={avatarUrl} alt={user?.full_name} className="object-cover" />
                    ) : null}
                    <AvatarFallback className="bg-gradient-to-br from-blue-600 to-cyan-500 text-white text-3xl font-bold">
                      {initials}
                    </AvatarFallback>
                  </Avatar>

                  {/* Hover Overlay */}
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-opacity duration-300">
                    <Camera className="w-6 h-6 text-white mb-1" />
                    <span className="text-[10px] text-slate-200 font-medium uppercase tracking-wider">
                      Upload Picture
                    </span>
                  </div>

                  {/* Uploading loader */}
                  {isUploading && (
                    <div className="absolute inset-0 bg-[#0A0F1C]/80 flex flex-col items-center justify-center">
                      <Loader2 className="w-6 h-6 animate-spin text-blue-400 mb-1" />
                      <span className="text-[10px] text-slate-300 font-medium">
                        {uploadProgress}%
                      </span>
                    </div>
                  )}
                </div>

                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept="image/png, image/jpeg, image/jpg, image/gif, image/webp"
                  className="hidden"
                />

                {user?.avatar_url && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDeleteAvatar}
                    disabled={isUploading}
                    className="mt-2.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10 h-7 px-2"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                    Remove picture
                  </Button>
                )}

                <div className="text-center mt-4">
                  <h2 className="text-lg font-bold text-white truncate max-w-[240px]">
                    {user?.full_name}
                  </h2>
                  <p className="text-xs text-slate-400 truncate max-w-[240px] mt-0.5">
                    {user?.email}
                  </p>
                  <div className="flex flex-col items-center gap-1.5 mt-3">
                    <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 capitalize">
                      {user?.role || 'Viewer'}
                    </Badge>
                    {user?.subscription_tier && (
                      <Badge className={
                        user.subscription_tier === 'pro' 
                          ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 capitalize animate-pulse font-mono text-[9px]'
                          : 'bg-slate-500/10 text-slate-400 border-slate-500/20 capitalize font-mono text-[9px]'
                      }>
                        {user.subscription_tier} Plan
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="w-full border-t border-white/[0.06] mt-6 pt-5 space-y-3.5">
                  <div className="flex items-center text-xs text-slate-400">
                    <Calendar className="w-4 h-4 mr-2.5 text-slate-500" />
                    <span>Registered on {user?.created_at ? parseDate(user.created_at).toLocaleDateString() : '—'}</span>
                  </div>
                  <div className="flex items-center text-xs text-slate-400">
                    <Shield className="w-4 h-4 mr-2.5 text-slate-500" />
                    <span className="capitalize">Role privileges: {user?.role || 'viewer'} levels</span>
                  </div>
                  <div className="flex items-center text-xs text-slate-400">
                    <CreditCard className="w-4 h-4 mr-2.5 text-slate-500" />
                    <span className="capitalize">Active Subscription: {user?.subscription_tier || 'free'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Quick stats card */}
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-white">Your Analytics Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-[#0A0F1C]/40 border border-white/[0.04]">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded bg-blue-500/10 text-blue-400">
                      <BarChart3 className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs text-slate-400">Total Forecasts Run</span>
                  </div>
                  <span className="text-sm font-bold text-white">
                    {loadingStats ? <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" /> : stats.totalForecasts}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-[#0A0F1C]/40 border border-white/[0.04]">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded bg-amber-500/10 text-amber-400">
                      <AlertCircle className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs text-slate-400">Unresolved Alerts</span>
                  </div>
                  <span className="text-sm font-bold text-white">
                    {loadingStats ? <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" /> : stats.activeAlerts}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-[#0A0F1C]/40 border border-white/[0.04]">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded bg-emerald-500/10 text-emerald-400">
                      <Cpu className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs text-slate-400">Avg Peak Power</span>
                  </div>
                  <span className="text-sm font-bold text-white">
                    {loadingStats ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" />
                    ) : stats.avgPeakPower ? (
                      `${stats.avgPeakPower.toFixed(2)} kW`
                    ) : (
                      '—'
                    )}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Edit Profile & Picture Upload Info */}
          <div className="space-y-6 lg:col-span-2">
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-lg text-white">Profile Information</CardTitle>
                <CardDescription className="text-slate-400">
                  Update your contact details and display names.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSaveProfile} className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="fullName" className="text-slate-300">Full Name</Label>
                      <div className="relative">
                        <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <Input
                          id="fullName"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          className="pl-9 bg-[#0A0F1C] border-white/10 text-white"
                          placeholder="Your Name"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email" className="text-slate-300">Email Address</Label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <Input
                          id="email"
                          type="email"
                          defaultValue={user?.email || ''}
                          className="pl-9 bg-[#0A0F1C] border-white/10 text-slate-400"
                          disabled
                        />
                      </div>
                      <p className="text-[10px] text-slate-500">Email addresses are tied to your single sign-on security configuration.</p>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-white/[0.06] flex justify-end">
                    <Button
                      type="submit"
                      disabled={isSavingProfile}
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      {isSavingProfile ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...
                        </>
                      ) : (
                        'Save Changes'
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

            {/* Profile Picture Upload Details Widget */}
            <Card className="bg-[#111827]/50 border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-base text-white">Upload New Profile Picture</CardTitle>
                <CardDescription className="text-slate-400">
                  Select or drag in an image file to set your profile picture.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                  onClick={triggerFileInput}
                  className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all ${
                    dragActive 
                      ? 'border-blue-500 bg-blue-500/10' 
                      : 'border-white/10 bg-[#0A0F1C]/40 hover:border-white/20 hover:bg-[#0A0F1C]/60'
                  }`}
                >
                  <div className="p-3 rounded-full bg-white/[0.02] border border-white/[0.06] mb-3 text-slate-400">
                    <Upload className="w-6 h-6 animate-pulse" />
                  </div>
                  <p className="text-sm font-medium text-white text-center">
                    Drag and drop your image here, or <span className="text-blue-400 underline">browse files</span>
                  </p>
                  <p className="text-xs text-slate-500 text-center mt-1">
                    Accepts PNG, JPG, JPEG, GIF or WebP. Maximum size: 2MB.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
