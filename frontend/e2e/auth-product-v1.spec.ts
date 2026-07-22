import { expect, type Page, test } from '@playwright/test';

const API = 'http://localhost:8000';
const USER = {
  id: 41,
  email: 'browser@example.com',
  full_name: 'Browser User',
  role: 'user',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-07-22T10:00:00Z',
};

async function mockAnonymousSession(page: Page, options: { email?: boolean; google?: boolean } = {}) {
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') {
      await route.fulfill({ status: 401, json: { detail: { code: 'refresh_session_missing', message: 'No session' } } });
    } else if (pathname === '/api/v1/auth/capabilities') {
      await route.fulfill({
        json: {
          email_delivery_enabled: options.email ?? true,
          google_auth_enabled: options.google ?? false,
          google_client_id: options.google ? 'browser-client.apps.example.test' : null,
        },
      });
    } else {
      await route.fulfill({ status: 404, json: { detail: { code: 'not_mocked', message: pathname } } });
    }
  });
}

test('registration is gated by mail readiness and creates no browser session', async ({ page }) => {
  await mockAnonymousSession(page, { email: false });
  await page.goto('/register');
  await expect(page.getByText('Registration is temporarily unavailable')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create account' })).toBeDisabled();

  await page.unroute(`${API}/**`);
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ status: 401, json: {} });
    if (pathname === '/api/v1/auth/capabilities') return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: false, google_client_id: null } });
    if (pathname === '/api/v1/auth/register') return route.fulfill({ status: 201, json: { message: 'Check your email.', verification_required: true } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.reload();
  await page.getByLabel('Full name').fill('Browser User');
  await page.getByLabel('Email').fill('Browser@Example.com');
  await page.getByLabel('Password', { exact: true }).fill('browser-password');
  await page.getByLabel('Confirm password').fill('browser-password');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/verify-email\/pending\?email=browser%40example.com/);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  expect((await page.context().cookies()).filter((cookie) => cookie.name === 'refresh_token')).toEqual([]);
});

test('verification, forgot-password, and reset routes expose explicit safe states', async ({ page }) => {
  await mockAnonymousSession(page);
  await page.goto('/verify-email');
  await expect(page.getByText('This verification link is missing its token.')).toBeVisible();

  await page.unroute(`${API}/**`);
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ status: 401, json: {} });
    if (pathname === '/api/v1/auth/verification/confirm') return route.fulfill({ json: { message: 'Email verified. You can now sign in.' } });
    if (pathname === '/api/v1/auth/password-reset/request') return route.fulfill({ status: 202, json: { message: 'If an account matches this email, reset instructions will be sent shortly.' } });
    if (pathname === '/api/v1/auth/password-reset/confirm') return route.fulfill({ json: { message: 'Password reset. Please sign in.' } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/verify-email?token=verification-token-value-12345');
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  await expect(page).toHaveURL('http://127.0.0.1:3100/verify-email');
  await page.goto('/forgot-password');
  await page.getByLabel('Email').fill('unknown@example.com');
  await page.getByRole('button', { name: 'Send reset instructions' }).click();
  await expect(page.getByText('If an account matches this email')).toBeVisible();
  await page.goto('/reset-password?token=password-reset-token-value-12345');
  await page.getByLabel('New password').fill('replacement-password');
  await page.getByLabel('Confirm password').fill('replacement-password');
  await page.getByRole('button', { name: 'Reset password' }).click();
  await expect(page.getByText('Password reset. Please sign in.')).toBeVisible();
  await expect(page).toHaveURL('http://127.0.0.1:3100/reset-password');
});

test('Google login is capability-gated and uses a controlled credential flow', async ({ page }) => {
  await mockAnonymousSession(page, { google: false });
  await page.goto('/login');
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toHaveCount(0);

  await page.unroute(`${API}/**`);
  await page.addInitScript(() => {
    let credentialCallback: ((value: { credential: string }) => void) | undefined;
    window.google = {
      accounts: {
        id: {
          initialize(options) { credentialCallback = options.callback; },
          prompt() { credentialCallback?.({ credential: 'controlled-google-credential-value' }); },
        },
      },
    };
  });
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ status: 401, json: {} });
    if (pathname === '/api/v1/auth/capabilities') return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: true, google_client_id: 'browser-client.apps.example.test' } });
    if (pathname === '/api/v1/auth/google/challenge') return route.fulfill({ json: { state: 'state-value-12345678901234567890', nonce: 'nonce-value-12345678901234567890', expires_in_seconds: 300 } });
    if (pathname === '/api/v1/auth/google') return route.fulfill({ json: { access_token: 'memory-access-token', token_type: 'bearer', user: USER } });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.reload();
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  expect(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }))).toEqual({ local: [], session: [] });
});

test('local login reloads from the HttpOnly session and logout sends no refresh token body', async ({ page }) => {
  let refreshCalls = 0;
  let logoutBody = 'unset';
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') {
      refreshCalls += 1;
      return route.fulfill({ json: { access_token: `memory-token-${refreshCalls}`, token_type: 'bearer' } });
    }
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/settings') return route.fulfill({ json: { country: 'Morocco', region: 'Casablanca-Settat', electricity_provider: 'ONEE', currency: 'MAD', peak_rate: 1.1, off_peak_rate: 0.8, peak_start_hour: 6, peak_end_hour: 22, sensor_type: 'simulator' } });
    if (pathname === '/api/v1/settings/budget') return route.fulfill({ json: null });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/auth/logout') {
      logoutBody = request.postData() ?? '';
      return route.fulfill({ json: { message: 'Logged out successfully' } });
    }
    if (pathname === '/api/v1/auth/capabilities') return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: false, google_client_id: null } });
    return route.fulfill({ status: 200, json: {} });
  });
  await page.goto('/settings');
  await expect(page).toHaveURL(/\/settings/);
  await page.reload();
  expect(refreshCalls).toBe(2);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);

  await page.locator('#sidebar-user-menu').click();
  await page.locator('#menu-logout').click();
  await expect(page).toHaveURL(/\/login/);
  expect(logoutBody).toBe('');
});
