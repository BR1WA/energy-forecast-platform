import { expect, type Page, test } from '@playwright/test';


const API = 'http://localhost:8000';
const USER = {
  id: 51,
  email: 'verified-alerts@example.com',
  full_name: 'Verified Alerts',
  role: 'user',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-07-22T10:00:00Z',
};

type CapabilityMode = 'available' | 'mail_disabled' | 'email_unverified' | 'failure';

async function mockAlertSettings(page: Page, options: {
  capability?: CapabilityMode;
  capabilityDelayMs?: number;
  alertsFail?: boolean;
  recommendationsFail?: boolean;
} = {}) {
  let capability = options.capability ?? 'mail_disabled';
  let emailEnabled = false;
  let savedPayload: Record<string, unknown> | null = null;

  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') {
      return route.fulfill({ json: { access_token: 'memory-alert-token', token_type: 'bearer' } });
    }
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/alerts' && request.method() === 'GET') {
      if (options.alertsFail) return route.fulfill({ status: 503, json: { detail: 'Alerts temporarily unavailable' } });
      return route.fulfill({
        json: [{
          id: 7,
          alert_type: 'high_consumption',
          severity: 'high',
          message: 'Measured demand exceeded the configured threshold.',
          state: 'open',
          is_acknowledged: false,
          evidence_json: { observed_kw: 4.2, threshold_kw: 3, source: 'push' },
          created_at: '2026-07-22T10:00:00Z',
          resolved_at: null,
        }],
      });
    }
    if (pathname === '/api/v1/recommendations' && request.method() === 'GET') {
      if (options.recommendationsFail) return route.fulfill({ status: 503, json: { detail: 'Recommendations temporarily unavailable' } });
      return route.fulfill({
        json: [{
          id: 12,
          alert_id: 7,
          category: 'peak_load',
          title: 'Reduce the active peak load',
          message: 'Move one flexible appliance outside the current peak.',
          status: 'open',
          estimated_excess_cost_per_hour_mad: 1.32,
          evidence_json: { observed_kw: 4.2, threshold_kw: 3 },
          created_at: '2026-07-22T10:00:00Z',
        }],
      });
    }
    if (pathname === '/api/v1/alerts/config' && request.method() === 'GET') {
      if (options.capabilityDelayMs) await new Promise((resolve) => setTimeout(resolve, options.capabilityDelayMs));
      if (capability === 'failure') return route.fulfill({ status: 503, json: { detail: 'Capability temporarily unavailable' } });
      const mailAvailable = capability === 'available';
      return route.fulfill({
        json: {
          id: 9,
          threshold_kw: 3,
          cooldown_minutes: 60,
          missing_data_minutes: 60,
          email_enabled: emailEnabled,
          email_delivery_available: mailAvailable,
          email_delivery_unavailable_reason: mailAvailable ? null : capability,
          created_at: '2026-07-22T10:00:00Z',
        },
      });
    }
    if (pathname === '/api/v1/alerts/config' && request.method() === 'POST') {
      savedPayload = request.postDataJSON() as Record<string, unknown>;
      emailEnabled = savedPayload.email_enabled === true;
      return route.fulfill({
        json: {
          id: 9,
          ...savedPayload,
          email_enabled: emailEnabled,
          email_delivery_available: true,
          email_delivery_unavailable_reason: null,
          created_at: '2026-07-22T10:00:00Z',
        },
      });
    }
    return route.fulfill({ status: 200, json: {} });
  });

  return {
    enableMail() { capability = 'available'; },
    savedPayload() { return savedPayload; },
  };
}


test('critical-alert email opt-in is capability-gated and explicit', async ({ page }) => {
  const mock = await mockAlertSettings(page);
  await page.goto('/actions');

  const preference = page.getByLabel('Email critical incidents');
  await expect(preference).toBeDisabled();
  await expect(page.getByText('Email delivery is unavailable.')).toBeVisible();

  mock.enableMail();
  await page.reload();
  await expect(preference).toBeEnabled();
  await expect(preference).not.toBeChecked();
  await preference.check();
  await page.getByRole('button', { name: 'Save rules' }).click();

  await expect(preference).toBeChecked();
  await expect(page.getByText('Enabled for newly created critical incidents.')).toBeVisible();
  await expect.poll(() => mock.savedPayload()).toMatchObject({
    threshold_kw: 3,
    cooldown_minutes: 60,
    missing_data_minutes: 60,
    email_enabled: true,
  });
});


test('unverified users receive the verification-specific email state', async ({ page }) => {
  await mockAlertSettings(page, { capability: 'email_unverified' });
  await page.goto('/actions');

  await expect(page.getByLabel('Email critical incidents')).toBeDisabled();
  await expect(page.getByText('Verify your email to enable email alerts.')).toBeVisible();
});


test('email capability has an explicit loading state', async ({ page }) => {
  await mockAlertSettings(page, { capability: 'available', capabilityDelayMs: 1_000 });
  await page.goto('/actions');

  await expect(page.getByText('Checking email delivery availability...')).toBeVisible();
  await expect(page.getByText('Off. Opt in to receive newly created critical incidents by email.')).toBeVisible();
});


test('capability failure remains unknown while incidents and recommendations still render', async ({ page }) => {
  await mockAlertSettings(page, { capability: 'failure' });
  await page.goto('/actions');

  await expect(page.getByText('Email delivery status is temporarily unavailable.')).toBeVisible();
  await expect(page.getByText('Email delivery is unavailable.')).toHaveCount(0);
  await expect(page.getByText('Measured demand exceeded the configured threshold.')).toBeVisible();
  await expect(page.getByText('Reduce the active peak load')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save rules' })).toBeDisabled();
});


test('alerts failure does not erase successful capability and recommendation state', async ({ page }) => {
  await mockAlertSettings(page, { capability: 'available', alertsFail: true });
  await page.goto('/actions');

  await expect(page.getByLabel('Email critical incidents')).toBeEnabled();
  await expect(page.getByText('Off. Opt in to receive newly created critical incidents by email.')).toBeVisible();
  await expect(page.getByText('Reduce the active peak load')).toBeVisible();
  await expect(page.getByText('Email delivery is unavailable.')).toHaveCount(0);
});


test('recommendations failure does not erase successful capability and incident state', async ({ page }) => {
  await mockAlertSettings(page, { capability: 'available', recommendationsFail: true });
  await page.goto('/actions');

  await expect(page.getByLabel('Email critical incidents')).toBeEnabled();
  await expect(page.getByText('Measured demand exceeded the configured threshold.')).toBeVisible();
  await expect(page.getByText('Off. Opt in to receive newly created critical incidents by email.')).toBeVisible();
  await expect(page.getByText('Email delivery is unavailable.')).toHaveCount(0);
});
