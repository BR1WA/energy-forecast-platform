import { expect, type Page, test } from '@playwright/test';


const API = 'http://localhost:8000';
const USER = {
  id: 61,
  email: 'owner@example.com',
  full_name: 'Product Owner',
  role: 'user',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-07-23T08:00:00Z',
  avatar_url: null,
};


test('public policy pages expose configured owner, contact, and effective date', async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ status: 401, json: {} });
    if (pathname === '/api/v1/system/legal') {
      return route.fulfill({
        json: {
          configured: true,
          owner_name: 'Energy Forecast Product',
          contact_email: 'legal@example.test',
          support_email: 'support@example.test',
          effective_date: '2026-07-23',
        },
      });
    }
    return route.fulfill({ status: 404, json: {} });
  });

  for (const [path, heading] of [['/privacy', 'Privacy'], ['/terms', 'Terms'], ['/support', 'Support']]) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: new RegExp(heading) })).toBeVisible();
    await expect(page.getByText('Energy Forecast Product')).toBeVisible();
    await expect(page.getByText('2026-07-23')).toBeVisible();
    await expect(page.locator('a[href^="mailto:"]')).toBeVisible();
  }
});


async function mockSettings(page: Page) {
  let deletionBody: Record<string, unknown> | null = null;
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'memory-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/settings') return route.fulfill({ json: { country: 'Morocco', region: 'Casablanca-Settat', electricity_provider: 'ONEE', currency: 'MAD', peak_rate: 1.1, off_peak_rate: 0.8, peak_start_hour: 6, peak_end_hour: 22, sensor_type: 'simulator' } });
    if (pathname === '/api/v1/settings/budget') return route.fulfill({ json: null });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/auth/capabilities') return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: false, google_client_id: null } });
    if (pathname === '/api/v1/account/deletion/capabilities') return route.fulfill({ json: { method: 'password', google_reauthentication_available: false } });
    if (pathname === '/api/v1/account/export') {
      return route.fulfill({ body: 'PK controlled archive', contentType: 'application/zip', headers: { 'content-disposition': 'attachment; filename="energy-account-export.zip"' } });
    }
    if (pathname === '/api/v1/account' && request.method() === 'DELETE') {
      deletionBody = request.postDataJSON() as Record<string, unknown>;
      return route.fulfill({ json: { message: 'Account deleted permanently' } });
    }
    return route.fulfill({ status: 200, json: {} });
  });
  return { deletionBody: () => deletionBody };
}


test('settings provides archive download and password-confirmed irreversible deletion', async ({ page }) => {
  const mock = await mockSettings(page);
  page.on('dialog', (dialog) => void dialog.accept());
  await page.goto('/settings');
  await page.getByRole('tab', { name: 'Security' }).click();
  await expect(page.getByText('Privacy controls')).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download account archive' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^energyforecast-account-\d{4}-\d{2}-\d{2}\.zip$/);

  await page.getByLabel('Password to delete account').fill('recent-password');
  await page.getByLabel('Type DELETE to confirm').fill('DELETE');
  await page.getByRole('button', { name: 'Permanently delete account' }).click();
  await expect(page).toHaveURL(/\/login/);
  await expect.poll(() => mock.deletionBody()).toEqual({ confirmation: 'DELETE', current_password: 'recent-password' });
});
