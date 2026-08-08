import { expect, type Page, test } from '@playwright/test';


const API = 'http://localhost:8000';
const ADMIN = {
  id: 1,
  email: 'admin@example.com',
  full_name: 'Release Admin',
  role: 'admin',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-08-01T08:00:00Z',
  avatar_url: null,
};
const USERS = [
  { ...ADMIN, lifecycle_status: 'active', created_at: '2026-08-01T08:00:00Z' },
  {
    id: 2,
    email: 'waiting@example.com',
    full_name: 'Waiting User',
    role: 'user',
    is_active: true,
    is_setup_complete: false,
    email_verified_at: null,
    lifecycle_status: 'pending_verification',
    created_at: '2026-08-02T08:00:00Z',
  },
  {
    id: 3,
    email: 'disabled@example.com',
    full_name: 'Disabled User',
    role: 'user',
    is_active: false,
    is_setup_complete: true,
    email_verified_at: '2026-08-03T08:00:00Z',
    lifecycle_status: 'disabled',
    created_at: '2026-08-03T08:00:00Z',
  },
];


async function mockAdmin(page: Page) {
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'admin-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: ADMIN });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/admin/users') return route.fulfill({ json: USERS });
    if (pathname === '/api/v1/admin/health') {
      return route.fulfill({
        json: {
          status: 'operational',
          total_users: 3,
          active_users: 1,
          pending_users: 1,
          disabled_users: 1,
          total_forecasts: 4,
          database_status: 'healthy',
          forecast_status: 'ready',
          forecast_error: null,
          model_name: 'Test model',
          model_version: 'test',
          artifact_fingerprint: 'fingerprint',
          uptime_seconds: 3600,
          cpu_usage: 10,
          memory_usage: 20,
        },
      });
    }
    if (pathname === '/api/v1/admin/model-readiness/all') {
      return route.fulfill({ json: { artifacts: [] } });
    }
    return route.fulfill({ status: 200, json: {} });
  });
}


test('Admin shows mutually exclusive lifecycle badges, counts, search, and filters', async ({ page }) => {
  await mockAdmin(page);
  await page.goto('/admin');

  await expect(page.getByRole('heading', { name: 'Administration' })).toBeVisible();
  await expect(page.getByText('Active users').locator('..').getByText('1', { exact: true })).toBeVisible();
  await expect(page.getByText('Pending verification').first().locator('..').getByText('1', { exact: true })).toBeVisible();
  await expect(page.getByText('Disabled users').locator('..').getByText('1', { exact: true })).toBeVisible();

  const table = page.getByRole('table');
  await expect(table.getByText('Pending verification')).toBeVisible();
  await expect(table.getByText('Active', { exact: true })).toBeVisible();
  await expect(table.getByText('Disabled', { exact: true })).toBeVisible();

  await page.getByLabel('Filter users by status').click();
  await page.getByRole('option', { name: 'Pending verification' }).click();
  await expect(table.getByText('waiting@example.com')).toBeVisible();
  await expect(table.getByText('admin@example.com')).toBeHidden();
  await expect(table.getByText('disabled@example.com')).toBeHidden();

  await page.getByPlaceholder('Search users').fill('missing user');
  await expect(table.getByText('No users match the current search and status filter.')).toBeVisible();
});
