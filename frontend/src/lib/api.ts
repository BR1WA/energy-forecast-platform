import type {
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  User,
  ForecastModel,
  ForecastResult,
  ForecastHistory,
  SampleDataset,
  AnalyticsSummary,
  Alert,
  AlertConfig,
  AdminUser,
  ModelRegistry,
  SystemHealth,
  CheckoutResponse,
  SubscriptionResponse,
  EntitlementsResponse,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================
// Token helpers
// ============================================================
function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('refresh_token');
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

// ============================================================
// Core fetch wrapper
// ============================================================
interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
  isBlob?: boolean;
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });

    if (!res.ok) {
      clearTokens();
      return null;
    }

    const data = await res.json();
    setTokens(data.access_token, refresh);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipAuth = false, isBlob = false, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    ...(customHeaders as Record<string, string>),
  };

  if (!(rest.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  if (!skipAuth) {
    const token = getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  let res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...rest,
    headers,
  });

  // If 401, try refreshing the token
  if (res.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`;
      res = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...rest,
        headers,
      });
    } else {
      clearTokens();
      if (typeof window !== 'undefined') {
        window.location.href = '/';
      }
      throw new Error('Session expired');
    }
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    if (res.status === 403 && typeof window !== 'undefined') {
      import('sonner').then(({ toast }) => {
        toast.error(errorData.detail || 'Access denied. Please upgrade your subscription plan.', {
          action: {
            label: 'Upgrade Plan',
            onClick: () => { window.location.href = '/plans'; }
          },
          duration: 10000,
        });
      }).catch(err => console.error('Failed to load sonner toast', err));
    }
    throw new Error(errorData.detail || `API error: ${res.status}`);
  }

  if (isBlob) {
    return res.blob() as unknown as T;
  }

  return res.json();
}

// ============================================================
// Auth API
// ============================================================
export const authApi = {
  login: (payload: LoginPayload): Promise<LoginResponse> =>
    apiFetch('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  register: (payload: RegisterPayload): Promise<LoginResponse> =>
    apiFetch('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
      skipAuth: true,
    }),

  getMe: (): Promise<User> => apiFetch('/api/v1/auth/me'),

  updateProfile: (data: { full_name?: string }): Promise<User> =>
    apiFetch('/api/v1/auth/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  updatePassword: (data: { current_password: string; new_password: string }): Promise<{ message: string }> =>
    apiFetch('/api/v1/auth/password', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  uploadAvatar: (file: File): Promise<User> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/api/v1/auth/me/avatar', {
      method: 'POST',
      body: formData,
    });
  },

  deleteAvatar: (): Promise<User> =>
    apiFetch('/api/v1/auth/me/avatar', {
      method: 'DELETE',
    }),
};

// ============================================================
// Billing API
// ============================================================
export const billingApi = {
  getEntitlements: (): Promise<EntitlementsResponse> =>
    apiFetch('/api/v1/billing/entitlements'),

  getSubscription: (): Promise<SubscriptionResponse | null> =>
    apiFetch('/api/v1/billing/subscription'),

  checkout: (tier: 'pro' | 'enterprise'): Promise<CheckoutResponse> =>
    apiFetch('/api/v1/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ tier }),
    }),

  confirmCheckout: (checkout_ref: string): Promise<User> =>
    apiFetch('/api/v1/billing/checkout/confirm', {
      method: 'POST',
      body: JSON.stringify({ checkout_ref }),
    }),

  cancelSubscription: (): Promise<User> =>
    apiFetch('/api/v1/billing/cancel', {
      method: 'POST',
    }),
};

// ============================================================
// Forecast API
// ============================================================
export const forecastApi = {
  getModels: (): Promise<ForecastModel[]> =>
    apiFetch('/api/v1/forecast/models'),

  predict: (modelName: string, data: File | string): Promise<ForecastResult> => {
    if (data instanceof File) {
      const formData = new FormData();
      formData.append('model_name', modelName);
      formData.append('file', data);

      return apiFetch('/api/v1/forecast/predict/upload', {
        method: 'POST',
        body: formData,
      });
    }

    // String = sample name
    return apiFetch('/api/v1/forecast/predict', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName, sample_name: data }),
    });
  },

  compare: (data: File | string): Promise<Record<string, unknown>> => {
    if (data instanceof File) {
      const formData = new FormData();
      formData.append('file', data);

      return apiFetch('/api/v1/forecast/compare/upload', {
        method: 'POST',
        body: formData,
      });
    }

    return apiFetch('/api/v1/forecast/compare', {
      method: 'POST',
      body: JSON.stringify({ sample_name: data }),
    });
  },

  predictSmartMeter: (modelName: string): Promise<ForecastResult> =>
    apiFetch('/api/v1/forecast/smart-meter/sync', {
      method: 'POST',
      body: JSON.stringify({ model_name: modelName }),
    }),

  compareSmartMeter: (): Promise<Record<string, unknown>> =>
    apiFetch('/api/v1/forecast/smart-meter/compare', {
      method: 'POST',
    }),

  getHistory: (): Promise<ForecastHistory[]> =>
    apiFetch('/api/v1/forecast/history'),

  getSamples: (): Promise<SampleDataset[]> =>
    apiFetch('/api/v1/forecast/samples'),
};

// ============================================================
// Analytics API
// ============================================================
export const analyticsApi = {
  getSummary: (): Promise<AnalyticsSummary> =>
    apiFetch('/api/v1/analytics/summary'),

  downloadReportPDF: (): Promise<Blob> =>
    apiFetch('/api/v1/analytics/report/pdf', { isBlob: true }),
};

// ============================================================
// Multi-Site API
// ============================================================
export const multiSiteApi = {
  getSites: (): Promise<{ data: any[] }> =>
    apiFetch('/api/v1/multi-site'),
};

// ============================================================
// Alerts API
// ============================================================
export const alertsApi = {
  getAlerts: async (): Promise<Alert[]> => {
    const raw = await apiFetch<any[]>('/api/v1/alerts');
    return raw.map((a) => ({
      id: String(a.id),
      type: a.alert_type,
      severity: a.severity,
      title: a.alert_type ? a.alert_type.replace(/_/g, ' ').toUpperCase() : 'ALERT',
      message: a.message || '',
      is_read: a.is_acknowledged,
      created_at: a.created_at,
    }));
  },

  getConfig: async (): Promise<AlertConfig> => {
    const raw = await apiFetch<any>('/api/v1/alerts/config');
    return {
      high_consumption_threshold: raw.threshold_kw,
      anomaly_sensitivity: 'medium',
      notification_email: raw.email_enabled,
      notification_push: true,
    };
  },

  configureAlerts: async (config: AlertConfig): Promise<AlertConfig> => {
    const backendPayload = {
      threshold_kw: config.high_consumption_threshold,
      email_enabled: config.notification_email,
    };
    const raw = await apiFetch<any>('/api/v1/alerts/config', {
      method: 'POST',
      body: JSON.stringify(backendPayload),
    });
    return {
      high_consumption_threshold: raw.threshold_kw,
      anomaly_sensitivity: config.anomaly_sensitivity,
      notification_email: raw.email_enabled,
      notification_push: config.notification_push,
    };
  },

  acknowledgeAlert: (alertId: string | number): Promise<void> =>
    apiFetch('/api/v1/alerts/acknowledge', {
      method: 'POST',
      body: JSON.stringify({ alert_id: Number(alertId) }),
    }),
};

// ============================================================
// Admin API
// ============================================================
export const adminApi = {
  getUsers: (): Promise<AdminUser[]> => apiFetch('/api/v1/admin/users'),

  updateUser: (
    id: string,
    data: Partial<User>
  ): Promise<User> =>
    apiFetch(`/api/v1/admin/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getModels: (): Promise<ModelRegistry[]> =>
    apiFetch('/api/v1/admin/models'),

  getHealth: (): Promise<SystemHealth> =>
    apiFetch('/api/v1/admin/health'),

  getStats: (): Promise<Record<string, unknown>> =>
    apiFetch('/api/v1/admin/stats'),

  retrainModel: (modelName: string): Promise<{ message: string }> =>
    apiFetch(`/api/v1/admin/models/${modelName}/retrain`, {
      method: 'POST',
    }),
};

// ============================================================
// Settings API
// ============================================================
export const settingsApi = {
  getSettings: (): Promise<any> =>
    apiFetch('/api/v1/settings'),

  getSetupStatus: (): Promise<{ is_setup_complete: boolean }> =>
    apiFetch('/api/v1/settings/setup-status'),

  postSetup: (data: any): Promise<any> =>
    apiFetch('/api/v1/settings/setup', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updatePreferences: (data: {
    theme?: string;
    language?: string;
    email_alerts?: boolean;
    push_alerts?: boolean;
  }): Promise<{ message: string; preferences: any }> =>
    apiFetch('/api/v1/settings/preferences', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};

// Export helpers for use in auth context
export { setTokens, clearTokens, getAccessToken };
