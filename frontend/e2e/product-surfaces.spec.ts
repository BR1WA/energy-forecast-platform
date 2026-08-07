import { expect, test } from '@playwright/test';


const API = 'http://localhost:8000';
const USER = {
  id: 71,
  email: 'journey@example.com',
  full_name: 'Journey User',
  role: 'user',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-07-23T08:00:00Z',
};


test('setup completes through the explicit simulator path', async ({ page }) => {
  let setupSaved = false;
  let setupPayload: Record<string, unknown> | null = null;
  let simulatorStarted = false;
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'setup-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: { ...USER, is_setup_complete: setupSaved } });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [{ id: 1, name: 'Primary meter', source_type: 'simulation', is_primary: true, expected_interval_seconds: 60, last_seen_at: null, push_key_configured: false }] });
    if (pathname === '/api/v1/settings/setup' && request.method() === 'POST') { setupPayload = request.postDataJSON() as Record<string, unknown>; setupSaved = true; return route.fulfill({ json: { is_setup_complete: true } }); }
    if (pathname === '/api/v1/settings/budget' && request.method() === 'POST') return route.fulfill({ json: { monthly_budget_mad: 400 } });
    if (pathname === '/api/v1/simulation/start') { simulatorStarted = true; return route.fulfill({ json: { is_running: true } }); }
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: setupSaved } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/setup');
  await expect(page.getByRole('heading', { name: 'Set up your energy workspace' })).toBeVisible();
  await expect(page.getByLabel('Electricity provider')).toHaveCount(0);
  await page.getByLabel('Region').selectOption('Marrakech-Safi');
  await page.getByRole('button', { name: /Next/ }).click();
  await page.getByRole('button', { name: /Next/ }).click();
  await page.getByRole('button', { name: 'Simulator' }).click();
  await page.getByRole('button', { name: 'Complete setup' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  expect(setupSaved).toBe(true);
  expect(setupPayload).toMatchObject({ region: 'Marrakech-Safi' });
  expect(setupPayload).not.toHaveProperty('country');
  expect(setupPayload).not.toHaveProperty('currency');
  expect(setupPayload).not.toHaveProperty('electricity_provider');
  expect(simulatorStarted).toBe(true);
});


function model(horizon: 24 | 168) {
  return { available: true, enabled: true, warmed: true, horizon_hours: horizon, name: `global_tft_${horizon}h`, display_name: `${horizon} hour TFT`, version: '1.0', artifact_fingerprint: `fingerprint-${horizon}`, error: null };
}


function forecast(horizon: 24 | 168) {
  const origin = new Date('2026-07-23T00:00:00Z');
  return {
    id: horizon,
    model_name: `global_tft_${horizon}h`, model_version: '1.0', method: 'global_tft', fallback_reason: null,
    unit: 'kWh', timezone: 'UTC', horizon_hours: horizon, input_start: '2026-07-09T00:00:00Z', input_end: origin.toISOString(),
    forecast_start: origin.toISOString(), forecast_end: new Date(origin.getTime() + horizon * 3600000).toISOString(), coverage_percent: 100,
    observed_hours: 336, maximum_gap_hours: 0, sources: ['push'], confidence_method: 'Controlled quantiles', artifact_fingerprint: `fingerprint-${horizon}`,
    points: Array.from({ length: horizon }, (_, index) => ({ timestamp: new Date(origin.getTime() + index * 3600000).toISOString(), p10_kwh: .8, p50_kwh: 1, p90_kwh: 1.2 })),
    created_at: origin.toISOString(),
  };
}


test('forecast journey switches between persisted 24-hour and 168-hour states', async ({ page }) => {
  const generatedHorizons: number[] = [];
  const exportedForecastIds: number[] = [];
  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    const request = route.request();
    const requestedBody = request.method() === 'POST' && pathname === '/api/v1/forecast/run'
      ? request.postDataJSON() as { horizon_hours: 24 | 168 }
      : null;
    const horizon = requestedBody?.horizon_hours ?? (url.searchParams.get('horizon_hours') === '168' ? 168 : 24);
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'forecast-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/forecast/capabilities') return route.fulfill({ json: { default_horizon_hours: 24, capabilities: [{ horizon_hours: 24, label: 'Next 24 hours', description: '24 hours', model: model(24) }, { horizon_hours: 168, label: 'Next 7 days', description: '168 hours', model: model(168) }] } });
    if (pathname === '/api/v1/forecast/readiness') return route.fulfill({ json: { horizon_hours: horizon, status: 'ready', ready_for_tft: true, fallback_available: true, required_hours: 336, minimum_coverage_percent: 90, maximum_allowed_gap_hours: 6, coverage_percent: 100, observed_hours: 336, missing_hours: 0, imputed_hours: 0, maximum_gap_hours: 0, unit: 'kWh', resolution: 'hourly', latest_reading_at: '2026-07-23T00:00:00Z', forecast_origin: '2026-07-23T00:00:00Z', reasons: [], model: model(horizon) } });
    if (pathname === '/api/v1/forecast/latest') return route.fulfill({ json: forecast(horizon) });
    if (pathname === '/api/v1/forecast/history') return route.fulfill({ json: [{ id: horizon, model_name: `global_tft_${horizon}h`, method: 'global_tft', horizon_hours: horizon, forecast_start: '2026-07-23T00:00:00Z', created_at: '2026-07-23T00:00:00Z' }] });
    if (pathname === '/api/v1/forecast/run') {
      generatedHorizons.push(horizon);
      return route.fulfill({ status: 201, json: forecast(horizon) });
    }
    if (pathname === '/api/v1/analytics/report/pdf') {
      exportedForecastIds.push(Number(url.searchParams.get('forecast_id')));
      return route.fulfill({ body: '%PDF-1.4 selected forecast', contentType: 'application/pdf' });
    }
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/forecast');
  await expect(page.getByRole('heading', { name: 'Next 24 hours energy forecast' })).toBeVisible();
  await expect(page.getByText('Hourly forecast')).toBeVisible();
  await page.getByRole('button', { name: 'Generate forecast' }).click();
  await expect.poll(() => generatedHorizons).toEqual([24]);
  const dayDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Forecast PDF' }).click();
  await dayDownload;
  expect(exportedForecastIds).toEqual([24]);

  await page.getByRole('link', { name: 'Next 7 days · 168h' }).click();
  await expect(page).toHaveURL(/\/forecast\?horizon=168$/);
  await expect(page.getByRole('heading', { name: 'Next 7 days · 168-hour energy forecast' })).toBeVisible();
  await expect(page.getByText('Daily week-ahead totals')).toBeVisible();
  await expect(page.getByText('168 hourly values')).toBeVisible();
  await page.getByRole('button', { name: 'Generate forecast' }).click();
  await expect.poll(() => generatedHorizons).toEqual([24, 168]);
  const weekDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Forecast PDF' }).click();
  await weekDownload;
  expect(exportedForecastIds).toEqual([24, 168]);

  await page.reload();
  await expect(page).toHaveURL(/\/forecast\?horizon=168$/);
  await expect(page.getByRole('heading', { name: 'Next 7 days · 168-hour energy forecast' })).toBeVisible();
  await page.getByRole('link', { name: 'Next 24 hours' }).click();
  await expect(page).toHaveURL(/\/forecast\?horizon=24$/);
  await expect(page.getByRole('heading', { name: 'Next 24 hours energy forecast' })).toBeVisible();
});


test('dashboard monitoring exposes a controlled live reading without browser token storage', async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).WebSocket = class {
      onopen: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor() { setTimeout(() => this.onopen?.(), 0); }
      send() { setTimeout(() => this.onmessage?.({ data: JSON.stringify({ type: 'snapshot', reading: { reading_id: 99, timestamp: '2026-07-23T00:00:00Z', active_power_kw: 2.75, voltage_v: 230, current_a: 12, source: 'push', quality: 'validated' } }) }), 0); }
      close() { this.onclose?.(); }
    };
  });
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'monitor-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged' || pathname === '/api/v1/alerts' || pathname === '/api/v1/recommendations') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/forecast/latest') return route.fulfill({ json: null });
    if (pathname === '/api/v1/consumption/statistics') return route.fulfill({ json: { coverage_pct: 100, tariff: { currency: 'MAD' }, budget: { target_mad: null, spent_mad: 0, projected_mad: 0 } } });
    if (pathname === '/api/v1/consumption/period') return route.fulfill({ json: { timeframe: 'today', site_name: 'Controlled site', timezone: 'UTC', period_start: '2026-07-23T00:00:00Z', period_end: '2026-07-23T01:00:00Z', granularity: 'minute', sample_count: 2, total_kwh: 1, estimated_cost: 1.1, currency: 'MAD', average_kw: 2, peak_kw: 2.75, peak_at: '2026-07-23T00:30:00Z', coverage_pct: 100, expected_samples: 2, sources: [{ source: 'push', sample_count: 2 }], freshness: { status: 'fresh', latest_reading_at: '2026-07-23T00:30:00Z', age_seconds: 0 }, points: [{ timestamp: '2026-07-23T00:00:00Z', average_kw: 2, min_kw: 2, max_kw: 2, energy_kwh: .5, sample_count: 1 }, { timestamp: '2026-07-23T00:30:00Z', average_kw: 2.75, min_kw: 2.75, max_kw: 2.75, energy_kwh: .5, sample_count: 1 }] } });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: 'Energy overview' })).toBeVisible();
  await page.getByRole('tab', { name: 'Live' }).click();
  await expect(page.getByText('Stream: connected')).toBeVisible();
  await expect(page.getByText('2.750 kW').first()).toBeVisible();
  expect(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }))).toEqual({ local: [], session: [] });
});


test('usage chart exposes truthful power, energy, range, and gap states', async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'usage-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [{ id: 1, name: 'Primary meter', source_type: 'csv', is_primary: true, expected_interval_seconds: 3600, last_seen_at: '2026-07-04T00:00:00Z', push_key_configured: false }] });
    if (pathname === '/api/v1/consumption/readings') return route.fulfill({ json: { items: [], next_cursor: null } });
    if (pathname === '/api/v1/consumption/period') return route.fulfill({ json: {
      timeframe: 'month', site_name: 'Jury demonstration site', timezone: 'Africa/Casablanca',
      period_start: '2026-07-01T00:00:00Z', period_end: '2026-07-05T00:00:00Z', granularity: 'day',
      sample_count: 72, total_kwh: 36.2, estimated_cost: 51.4, currency: 'MAD', average_kw: 1.52,
      peak_kw: 3.84, peak_at: '2026-07-04T18:00:00Z', coverage_pct: 75,
      sources: [{ source: 'csv', count: 72 }],
      freshness: { status: 'historical', age_seconds: 3600, expected_interval_seconds: 3600, last_seen_at: '2026-07-04T00:00:00Z', source: 'csv', quality: 'validated' },
      points: [
        { timestamp: '2026-07-01T00:00:00Z', average_kw: 1.2, min_kw: .6, max_kw: 2.1, energy_kwh: 10.4, sample_count: 24 },
        { timestamp: '2026-07-02T00:00:00Z', average_kw: 1.5, min_kw: .7, max_kw: 2.8, energy_kwh: 12.1, sample_count: 24 },
        { timestamp: '2026-07-04T00:00:00Z', average_kw: 1.8, min_kw: .8, max_kw: 3.84, energy_kwh: 13.7, sample_count: 24 },
      ],
    } });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/usage');
  await expect(page.getByRole('main').getByRole('heading', { name: 'Usage' })).toBeVisible();
  await expect(page.getByText('Load and energy profile')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Power' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Observed min-max')).toBeVisible();
  await expect(page.getByText(/1 measurement gap shown as a break/)).toBeVisible();
  await expect(page.getByText('75.0% coverage')).toBeVisible();

  await page.getByRole('button', { name: 'Energy' }).click();
  await expect(page.getByRole('button', { name: 'Energy' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Energy per bucket')).toBeVisible();
  await expect(page.locator('.recharts-bar-rectangle')).toHaveCount(3);
});
