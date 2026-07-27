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


async function mockAlertSettings(page: Page) {
  let mailAvailable = false;
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
    if (pathname === '/api/v1/alerts' && request.method() === 'GET') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/recommendations' && request.method() === 'GET') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/alerts/config' && request.method() === 'GET') {
      return route.fulfill({
        json: {
          id: 9,
          threshold_kw: 3,
          cooldown_minutes: 60,
          missing_data_minutes: 60,
          email_enabled: emailEnabled,
          email_delivery_available: mailAvailable,
          email_delivery_unavailable_reason: mailAvailable ? null : 'mail_disabled',
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
    enableMail() { mailAvailable = true; },
    savedPayload() { return savedPayload; },
  };
}


test('critical-alert email opt-in is capability-gated and explicit', async ({ page }) => {
  const mock = await mockAlertSettings(page);
  await page.goto('/actions');

  const preference = page.getByLabel('Email critical incidents');
  await expect(preference).toBeDisabled();
  await expect(page.getByText('Email delivery is unavailable; incidents remain in the app.')).toBeVisible();

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
