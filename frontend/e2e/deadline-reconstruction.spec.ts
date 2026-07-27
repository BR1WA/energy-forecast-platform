import { expect, test, type Page } from '@playwright/test';

const API = 'http://localhost:8000';
const USER = {
  id: 91,
  email: 'deadline@example.com',
  full_name: 'Deadline User',
  role: 'user',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-07-27T08:00:00Z',
};

async function mockAuthenticatedApi(page: Page) {
  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'deadline-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/config') {
      return route.fulfill({
        json: {
          threshold_kw: 3,
          cooldown_minutes: 60,
          missing_data_minutes: 60,
          email_enabled: false,
          email_delivery_available: true,
          email_delivery_unavailable_reason: null,
        },
      });
    }
    if (pathname === '/api/v1/alerts') {
      return route.fulfill({
        json: [{
          id: 7,
          alert_type: 'high_consumption',
          severity: 'high',
          message: 'Measured demand exceeded the configured threshold.',
          state: 'open',
          is_acknowledged: false,
          evidence_json: { observed_kw: 4.2, threshold_kw: 3, source: 'push' },
          created_at: '2026-07-27T08:00:00Z',
          resolved_at: null,
        }],
      });
    }
    if (pathname === '/api/v1/recommendations') {
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
          created_at: '2026-07-27T08:00:00Z',
        }],
      });
    }
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    return route.fulfill({ status: 200, json: {} });
  });
}

test('deadline navigation and Actions present one coherent workflow', async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.goto('/actions');

  const primaryNav = page.locator('#sidebar nav a');
  await expect(primaryNav).toHaveCount(5);
  expect(await primaryNav.evaluateAll((links) => links.map((link) => link.getAttribute('href')))).toEqual(['/dashboard', '/usage', '/forecast', '/actions', '/settings']);
  await expect(page.getByRole('link', { name: 'Reports' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Simulator' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Admin/ })).toHaveCount(0);

  await expect(page.getByRole('main').getByRole('heading', { name: 'Actions' })).toBeVisible();
  await expect(page.getByText('Measured demand exceeded the configured threshold.')).toBeVisible();
  await expect(page.getByText('Reduce the active peak load')).toBeVisible();
  await expect(page.getByText(/4\.200 kW against the configured 3\.000 kW threshold/)).toBeVisible();
});

test('legacy report route and forecast sample preserve the deadline paths', async ({ page, request }) => {
  await mockAuthenticatedApi(page);
  await page.goto('/reports');
  await expect(page).toHaveURL(/\/usage$/);

  const response = await request.get('/samples/forecast-ready');
  expect(response.ok()).toBe(true);
  expect(response.headers()['content-disposition']).toContain('energyai-forecast-ready-14-days.csv');
  const csv = await response.text();
  expect(csv.trimEnd().split('\n')).toHaveLength(338);
  expect(csv).toContain('timestamp,active_power_kw,voltage_v,current_a');
});
