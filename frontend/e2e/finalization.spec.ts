import { expect, test } from '@playwright/test';

const API = 'http://localhost:8000';
const USER = {
  id: 98,
  email: 'final-user@example.com',
  full_name: 'Final User',
  role: 'user',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-07-27T08:00:00Z',
};

test('normal-user search hides Admin and site settings expose only real Morocco choices', async ({ page }) => {
  let savedSetup: Record<string, unknown> | null = null;
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'final-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/auth/capabilities') return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: false, google_client_id: null } });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/settings' && request.method() === 'GET') return route.fulfill({ json: { country: 'France', region: 'Casablanca-Settat', electricity_provider: 'Legacy provider', currency: 'EUR', peak_rate: 1.1, off_peak_rate: 0.8, peak_start_hour: 6, peak_end_hour: 22, sensor_type: 'csv' } });
    if (pathname === '/api/v1/settings/setup' && request.method() === 'POST') {
      savedSetup = request.postDataJSON() as Record<string, unknown>;
      return route.fulfill({ json: { message: 'Saved', settings: { ...savedSetup, country: 'Morocco', currency: 'MAD', electricity_provider: null } } });
    }
    if (pathname === '/api/v1/settings/budget' && request.method() === 'GET') return route.fulfill({ json: null });
    if (pathname === '/api/v1/settings/budget' && request.method() === 'PUT') return route.fulfill({ json: { monthly_budget_mad: 400 } });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/account/deletion/capabilities') return route.fulfill({ json: { method: 'password', google_reauthentication_available: false } });
    if (pathname === '/api/v1/alerts') return route.fulfill({ json: [] });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  await expect(page.getByText('Morocco', { exact: true })).toBeVisible();
  await expect(page.getByText('MAD', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Provider')).toHaveCount(0);
  await expect(page.getByLabel('Currency')).toHaveCount(0);
  await page.getByLabel('Region').selectOption('Souss-Massa');

  await page.locator('#navbar-search').click();
  await page.getByPlaceholder('Search pages...').fill('admin');
  await expect(page.getByText('No results found')).toBeVisible();
  await expect(page.getByText('Admin Panel', { exact: true })).toHaveCount(0);
  await page.getByPlaceholder('Search pages...').press('Enter');
  await expect(page).toHaveURL(/\/settings$/);

  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Save site settings' }).click();
  await expect.poll(() => savedSetup).not.toBeNull();
  expect(savedSetup).toMatchObject({ region: 'Souss-Massa', sensor_type: 'csv' });
  expect(savedSetup).not.toHaveProperty('country');
  expect(savedSetup).not.toHaveProperty('currency');
  expect(savedSetup).not.toHaveProperty('electricity_provider');
  expect(savedSetup).not.toHaveProperty('timezone');
});

test('registration remains identity-only and explains the Morocco setup step', async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ status: 401, json: {} });
    if (pathname === '/api/v1/auth/capabilities') return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: false, google_client_id: null } });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/register');
  await expect(page.getByText(/setup creates a Morocco-based private site/)).toBeVisible();
  await expect(page.getByLabel('Full name')).toBeVisible();
  await expect(page.getByLabel('Email')).toBeVisible();
  await expect(page.getByLabel('Country')).toHaveCount(0);
  await expect(page.getByLabel('Region')).toHaveCount(0);
  await expect(page.getByLabel('Provider')).toHaveCount(0);
  await expect(page.getByLabel('Currency')).toHaveCount(0);
});

test('settings preserve a zero budget and persist language changes', async ({ page }) => {
  let savedPreferences: Record<string, unknown> | null = null;
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'preferences-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/auth/capabilities') return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: false, google_client_id: null } });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/settings' && request.method() === 'GET') return route.fulfill({ json: { country: 'Morocco', region: 'Casablanca-Settat', electricity_provider: null, currency: 'MAD', peak_rate: 1.1, off_peak_rate: 0.8, peak_start_hour: 6, peak_end_hour: 22, sensor_type: 'csv' } });
    if (pathname === '/api/v1/settings/budget' && request.method() === 'GET') return route.fulfill({ json: { monthly_budget_mad: 0 } });
    if (pathname === '/api/v1/settings/preferences' && request.method() === 'PUT') {
      savedPreferences = request.postDataJSON() as Record<string, unknown>;
      return route.fulfill({ json: { message: 'Saved', preferences: savedPreferences } });
    }
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/account/deletion/capabilities') return route.fulfill({ json: { method: 'password', google_reauthentication_available: false } });
    if (pathname === '/api/v1/alerts') return route.fulfill({ json: [] });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/settings?tab=budget');
  await expect(page.getByLabel('Budget (MAD)')).toHaveValue('0');
  await page.getByRole('tab', { name: 'Preferences' }).click();
  await page.getByLabel('Language Selection').selectOption('fr');
  await expect.poll(() => savedPreferences).toEqual({ language: 'fr' });
  await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
});
