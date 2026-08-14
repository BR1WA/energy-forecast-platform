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
    unit: 'kWh', timezone: 'UTC', horizon_hours: horizon, target_count: horizon, target_interval_hours: 1, resolution: 'hourly', input_start: '2026-07-09T00:00:00Z', input_end: origin.toISOString(),
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
    if (pathname === '/api/v1/forecast/capabilities') return route.fulfill({ json: { default_horizon_hours: 24, capabilities: [{ horizon_hours: 24, target_count: 24, target_interval_hours: 1, resolution: 'hourly', label: 'Next 24 hours', description: '24 hours', model: model(24) }, { horizon_hours: 168, target_count: 168, target_interval_hours: 1, resolution: 'hourly', label: 'Next 7 days', description: '168 hours', model: model(168) }] } });
    if (pathname === '/api/v1/forecast/readiness') return route.fulfill({ json: { horizon_hours: horizon, target_count: horizon, target_interval_hours: 1, status: 'ready', ready_for_model: true, ready_for_tft: true, fallback_available: true, required_hours: 336, required_days: null, minimum_coverage_percent: 90, maximum_allowed_gap_hours: 6, coverage_percent: 100, observed_hours: 336, missing_hours: 0, imputed_hours: 0, maximum_gap_hours: 0, observed_days: 0, missing_days: 0, imputed_days: 0, maximum_gap_days: 0, unit: 'kWh', resolution: 'hourly', latest_reading_at: '2026-07-23T00:00:00Z', forecast_origin: '2026-07-23T00:00:00Z', reasons: [], model: model(horizon) } });
    if (pathname === '/api/v1/forecast/latest') return route.fulfill({ json: forecast(horizon) });
    if (pathname === '/api/v1/forecast/history') return route.fulfill({ json: [{ id: horizon, model_name: `global_tft_${horizon}h`, method: 'global_tft', horizon_hours: horizon, target_count: horizon, target_interval_hours: 1, resolution: 'hourly', forecast_start: '2026-07-23T00:00:00Z', created_at: '2026-07-23T00:00:00Z' }] });
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

  await page.getByRole('link', { name: 'Next 7 days' }).click();
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
  await expect(page.getByText('For today, your site used 1.00 kWh, costing about MAD 1.10.')).toBeVisible();
  await expect(page.getByText('Demand was highest at 2.75 kW around')).toBeVisible();
  await expect(page.getByText('Your power pattern')).toBeVisible();
  await page.getByRole('tab', { name: 'Live' }).click();
  await expect(page.getByText('Stream: connected')).toBeVisible();
  await expect(page.getByText('2.750 kW').first()).toBeVisible();
  expect(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }))).toEqual({ local: [], session: [] });
});


test('persistent simulator explains history and confirms simulator-only reset', async ({ page }) => {
  let resetCalled = false;
  const simulatorStatus = () => ({
    status: resetCalled ? 'reset' : 'stopped', is_running: false, uptime: 0, site_id: 1,
    base_load_kw: 1.2, variation_percent: 10, profile: 'household_v1', is_reproducible: true,
    bootstrap_days: 30, bootstrap_interval_minutes: 15, minimum_forecast_history_hours: 336,
    history_points: resetCalled ? 2881 : 120, history_start_at: '2026-07-10T12:00:00Z',
    history_end_at: '2026-08-09T12:00:00Z', history_span_hours: resetCalled ? 720 : 30,
    history_ready_for_forecast: resetCalled, continuity_enabled_at: null, last_catch_up_at: null,
    last_catch_up_points: 0, last_catch_up_interval_minutes: null, last_catch_up_was_limited: false,
    deleted_simulation_readings: resetCalled ? 120 : undefined, preserved_non_simulation_data: resetCalled,
  });
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'simulation-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/simulation/status') return route.fulfill({ json: simulatorStatus() });
    if (pathname === '/api/v1/simulation/reset') { resetCalled = true; return route.fulfill({ json: simulatorStatus() }); }
    if (pathname === '/api/v1/consumption/period') return route.fulfill({ json: {
      timeframe: 'live', site_name: 'Demo home', timezone: 'UTC', period_start: '2026-08-09T11:45:00Z',
      period_end: '2026-08-09T12:00:00Z', granularity: 'minute', total_kwh: 0, estimated_cost: 0,
      currency: 'MAD', average_kw: 0, peak_kw: 0, peak_at: null, coverage_pct: 0, sample_count: 0,
      sources: [], freshness: { status: 'empty', age_seconds: null, expected_interval_seconds: 5, last_seen_at: null, source: null, quality: null }, points: [],
    } });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/simulation');
  await expect(page.getByRole('heading', { name: 'Demo simulator' })).toBeVisible();
  await expect(page.getByText('30 hours')).toBeVisible();
  await expect(page.getByText('Synthetic, never measured')).toBeVisible();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Reset demo data' }).click();
  await expect.poll(() => resetCalled).toBe(true);
  await expect(page.getByText('720 hours')).toBeVisible();
  await expect(page.getByText('History available')).toBeVisible();
  await page.getByRole('button', { name: 'Stop demo and use real data' }).click();
  await expect(page).toHaveURL(/\/usage#csv-import$/);
});


test('CSV import stops a running simulator after confirmation and preserves the preview flow', async ({ page }) => {
  let simulatorRunning = true;
  const writeOrder: string[] = [];
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'csv-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [{ id: 1, name: 'Primary meter', source_type: 'simulation', is_primary: true, expected_interval_seconds: 900, last_seen_at: '2026-08-09T12:00:00Z', push_key_configured: false }] });
    if (pathname === '/api/v1/simulation/status') return route.fulfill({ json: { is_running: simulatorRunning } });
    if (pathname === '/api/v1/simulation/stop') {
      writeOrder.push('stop');
      simulatorRunning = false;
      return route.fulfill({ json: { is_running: false } });
    }
    if (pathname === '/api/v1/ingestion/meters/1/csv/preview') {
      return route.fulfill({ json: { mapped_columns: ['timestamp', 'active_power_kw'], valid_rows: 1, rejected_rows: 0, errors: [] } });
    }
    if (pathname === '/api/v1/ingestion/meters/1/csv/import') {
      writeOrder.push('import');
      return route.fulfill({ json: { accepted_rows: 1, duplicate_rows: 0, rejected_rows: 0 } });
    }
    if (pathname === '/api/v1/consumption/readings') return route.fulfill({ json: { items: [], next_cursor: null } });
    if (pathname === '/api/v1/consumption/period') return route.fulfill({ json: {
      timeframe: 'month', site_name: 'CSV handoff site', timezone: 'UTC',
      period_start: '2026-08-01T00:00:00Z', period_end: '2026-08-09T12:00:00Z', granularity: 'day',
      sample_count: 0, total_kwh: 0, estimated_cost: 0, currency: 'MAD', average_kw: 0,
      peak_kw: 0, peak_at: null, coverage_pct: 0, expected_samples: 0, sources: [],
      freshness: { status: 'empty', age_seconds: null, expected_interval_seconds: 900, last_seen_at: null, source: null, quality: null },
      points: [],
    } });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/usage#csv-import');
  await expect(page.getByText('The demo simulator is running. You can preview a CSV now')).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: 'measured-readings.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('timestamp,active_power_kw\n2026-08-09T12:00:00Z,1.2\n'),
  });
  await expect(page.getByText('1 valid, 0 rejected')).toBeVisible();
  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toBe('The demo simulator is currently running. Importing measured data while simulation continues may mix synthetic and imported readings. Stop the simulator and continue?');
    await dialog.accept();
  });
  await page.getByRole('button', { name: 'Import validated rows' }).click();
  await expect.poll(() => writeOrder).toEqual(['stop', 'import']);
  await expect(page.getByText('Imported 1 reading(s); 0 duplicate(s) skipped.')).toBeVisible();
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
  await expect(page.getByRole('tab', { name: 'Week' })).toBeVisible();
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


test('all timeframe displays aggregated monthly history with distinct month labels', async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'all-timeframe-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [{ id: 1, name: 'Primary meter', source_type: 'csv', is_primary: true, expected_interval_seconds: 3600, last_seen_at: '2026-03-31T00:00:00Z', push_key_configured: false }] });
    if (pathname === '/api/v1/consumption/readings') return route.fulfill({ json: { items: [], next_cursor: null } });
    if (pathname === '/api/v1/consumption/period') return route.fulfill({ json: {
      timeframe: 'all', site_name: 'Historical multi-year site', timezone: 'UTC',
      period_start: '2026-01-01T00:00:00Z', period_end: '2026-03-31T23:59:59Z', granularity: 'month',
      sample_count: 2160, total_kwh: 450.0, estimated_cost: 675.0, currency: 'MAD', average_kw: 1.25,
      peak_kw: 3.5, peak_at: '2026-02-15T12:00:00Z', coverage_pct: 100,
      sources: [{ source: 'csv', count: 2160 }],
      freshness: { status: 'historical', age_seconds: 3600, expected_interval_seconds: 3600, last_seen_at: '2026-03-31T23:59:59Z', source: 'csv', quality: 'validated' },
      points: [
        { timestamp: '2026-01-01T00:00:00Z', average_kw: 1.1, min_kw: 0.5, max_kw: 2.8, energy_kwh: 150.0, sample_count: 744 },
        { timestamp: '2026-02-01T00:00:00Z', average_kw: 1.3, min_kw: 0.6, max_kw: 3.5, energy_kwh: 140.0, sample_count: 672 },
        { timestamp: '2026-03-01T00:00:00Z', average_kw: 1.2, min_kw: 0.5, max_kw: 3.0, energy_kwh: 160.0, sample_count: 744 },
      ],
    } });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/usage');
  await page.getByRole('tab', { name: 'All' }).click();
  await expect(page.getByRole('button', { name: 'Energy' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('Energy per month bucket (kWh)')).toBeVisible();
  await expect(page.locator('.recharts-bar-rectangle')).toHaveCount(3);
  await expect(page.locator('svg.recharts-surface text').filter({ hasText: /Jan 26/ })).toBeVisible();
  await expect(page.locator('svg.recharts-surface text').filter({ hasText: /Feb 26/ })).toBeVisible();
  await expect(page.locator('svg.recharts-surface text').filter({ hasText: /Mar 26/ })).toBeVisible();
});


test('all timeframe daily overview displays candidate ticks on desktop and remains responsive on mobile', async ({ page }) => {
  const dailyPoints = Array.from({ length: 18 }, (_, i) => {
    const day = (i + 1).toString().padStart(2, '0');
    return {
      timestamp: `2026-07-${day}T00:00:00Z`,
      average_kw: 1.2 + (i % 5) * 0.1,
      min_kw: 0.5,
      max_kw: 2.0 + (i % 4) * 0.2,
      energy_kwh: 15.0 + i,
      sample_count: 24,
    };
  });

  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'daily-all-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [{ id: 1, name: 'Primary meter', source_type: 'csv', is_primary: true, expected_interval_seconds: 3600, last_seen_at: '2026-07-18T00:00:00Z', push_key_configured: false }] });
    if (pathname === '/api/v1/consumption/readings') return route.fulfill({ json: { items: [], next_cursor: null } });
    if (pathname === '/api/v1/consumption/period') return route.fulfill({ json: {
      timeframe: 'all', site_name: 'Daily 18-day site', timezone: 'UTC',
      period_start: '2026-07-01T14:37:00Z', period_end: '2026-07-18T23:59:59Z', granularity: 'day',
      sample_count: 432, total_kwh: 270.0, estimated_cost: 350.0, currency: 'MAD', average_kw: 1.35,
      peak_kw: 2.8, peak_at: '2026-07-10T12:00:00Z', coverage_pct: 100,
      sources: [{ source: 'csv', count: 432 }],
      freshness: { status: 'historical', age_seconds: 3600, expected_interval_seconds: 3600, last_seen_at: '2026-07-18T23:59:59Z', source: 'csv', quality: 'validated' },
      points: dailyPoints,
    } });
    return route.fulfill({ status: 200, json: {} });
  });

  // Desktop viewport: 18 daily bars render with clear candidate date labels
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.goto('/usage');
  await page.getByRole('tab', { name: 'All' }).click();
  await expect(page.locator('.recharts-bar-rectangle')).toHaveCount(18);
  await expect(page.getByText('Energy per day bucket (kWh)')).toBeVisible();
  await expect(page.locator('svg.recharts-surface')).toBeVisible();
  await expect(page.locator('.recharts-xAxis-ticks')).toBeAttached();

  // Mobile viewport: chart renders 18 bars responsively without crashing or horizontal overflow
  await page.setViewportSize({ width: 360, height: 640 });
  await expect(page.locator('.recharts-bar-rectangle')).toHaveCount(18);
  await expect(page.getByText('Energy per day bucket (kWh)')).toBeVisible();
});


test('usage page renders end-of-period projections for available and unavailable states', async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'projection-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/ingestion/meters') return route.fulfill({ json: [{ id: 1, name: 'Primary meter', source_type: 'csv', is_primary: true, expected_interval_seconds: 3600, last_seen_at: '2026-07-23T12:00:00Z', push_key_configured: false }] });
    if (pathname === '/api/v1/consumption/readings') return route.fulfill({ json: { items: [], next_cursor: null } });
    if (pathname === '/api/v1/consumption/period') {
      const url = new URL(route.request().url());
      const tf = url.searchParams.get('timeframe') || 'month';
      if (tf === 'month') {
        return route.fulfill({ json: {
          timeframe: 'month', site_name: 'Projection Site', timezone: 'UTC',
          period_start: '2026-07-01T00:00:00Z', period_end: '2026-07-15T12:00:00Z', granularity: 'day',
          sample_count: 348, total_kwh: 84.3, estimated_cost: 110.0, currency: 'MAD', average_kw: 1.25,
          peak_kw: 3.2, peak_at: '2026-07-10T14:00:00Z', coverage_pct: 98.5,
          sources: [{ source: 'csv', count: 348 }],
          freshness: { status: 'fresh', age_seconds: 60, expected_interval_seconds: 3600, last_seen_at: '2026-07-15T12:00:00Z', source: 'csv', quality: 'validated' },
          points: [
            { timestamp: '2026-07-01T00:00:00Z', average_kw: 1.2, min_kw: 0.5, max_kw: 3.0, energy_kwh: 28.0, sample_count: 24 },
          ],
          projection: {
            is_available: true,
            reason: null,
            projected_kwh: 302.7,
            projected_cost: 286.0,
            budget_target: 280.0,
            budget_status: 'projected_to_exceed',
            currency: 'MAD',
          },
        } });
      }
      if (tf === 'today') {
        return route.fulfill({ json: {
          timeframe: 'today', site_name: 'Projection Site', timezone: 'UTC',
          period_start: '2026-07-15T00:00:00Z', period_end: '2026-07-15T01:30:00Z', granularity: 'minute',
          sample_count: 90, total_kwh: 3.0, estimated_cost: 3.0, currency: 'MAD', average_kw: 2.0,
          peak_kw: 2.5, peak_at: '2026-07-15T01:00:00Z', coverage_pct: 100.0,
          sources: [{ source: 'csv', count: 90 }],
          freshness: { status: 'fresh', age_seconds: 60, expected_interval_seconds: 60, last_seen_at: '2026-07-15T01:30:00Z', source: 'csv', quality: 'validated' },
          points: [],
          projection: {
            is_available: false,
            reason: 'early_period',
            projected_kwh: null,
            projected_cost: null,
            budget_target: null,
            budget_status: null,
            currency: null,
          },
        } });
      }
      return route.fulfill({ json: {
        timeframe: 'all', site_name: 'Projection Site', timezone: 'UTC',
        period_start: '2026-01-01T00:00:00Z', period_end: '2026-07-15T12:00:00Z', granularity: 'month',
        sample_count: 1000, total_kwh: 1200.0, estimated_cost: 1500.0, currency: 'MAD', average_kw: 1.2,
        peak_kw: 3.5, peak_at: null, coverage_pct: 100.0,
        sources: [{ source: 'csv', count: 1000 }],
        freshness: { status: 'historical', age_seconds: 3600, expected_interval_seconds: 3600, last_seen_at: null, source: 'csv', quality: 'validated' },
        points: [],
        projection: {
          is_available: false,
          reason: 'unsupported_timeframe',
        },
      } });
    }
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/usage');

  // Month view shows End-of-period projection with budget exceedance
  const projectionCard = page.locator('.rounded-lg', { hasText: 'End-of-period projection' });
  await expect(projectionCard).toBeVisible();
  await expect(projectionCard.getByText('Deterministic estimate based on measured usage and configured tariff rates.')).toBeVisible();
  await expect(projectionCard.getByText('84.30 kWh')).toBeVisible();
  await expect(projectionCard.getByText('~302.70 kWh')).toBeVisible();
  await expect(projectionCard.getByText('~MAD 286.00')).toBeVisible();
  await expect(projectionCard.getByText('MAD 280.00')).toBeVisible();
  await expect(projectionCard.getByText('Projected to exceed budget')).toBeVisible();

  // Switch to Today: early period state shows explanation message
  await page.getByRole('tab', { name: 'Today' }).click();
  await expect(page.locator('.rounded-lg', { hasText: 'End-of-period projection' })).toBeVisible();
  await expect(page.getByText('Estimate available after more usage data is collected for this period.')).toBeVisible();

  // Switch to All: projection card is not displayed for All
  await page.getByRole('tab', { name: 'All' }).click();
  await expect(page.getByText('End-of-period projection')).toHaveCount(0);
});


test('dashboard renders truthful monthly budget projection states without relabeling measured cost', async ({ page }) => {
  let projectionAvailable = true;
  let projectionReason: string | null = null;
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'dash-budget-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts/unacknowledged' || pathname === '/api/v1/alerts') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/recommendations') return route.fulfill({ json: [{ id: 8, alert_id: null, category: 'peak_load', title: 'Shift flexible loads away from the evening peak', message: 'Move discretionary appliances after 22:00.', status: 'open', evidence_json: {}, created_at: '2026-08-08T18:00:00Z' }] });
    if (pathname === '/api/v1/forecast/latest') return route.fulfill({ json: null });
    if (pathname === '/api/v1/consumption/statistics') {
      return route.fulfill({ json: {
        month: '2026-08',
        total_kwh: 72.0,
        total_cost: 84.2,
        peak_kw: 3.4,
        average_daily_kwh: 9.0,
        days_elapsed: 8,
        days_in_month: 31,
        coverage_pct: 95.0,
        tariff: { currency: 'MAD', peak_rate: 1.1, off_peak_rate: 0.8, peak_start_hour: 6, peak_end_hour: 22 },
        budget: {
          target_mad: 280.0,
          spent_mad: 84.2,
          remaining_mad: 195.8,
          progress_pct: 30.1,
          projected_mad: projectionAvailable ? 302.7 : null,
          projection_available: projectionAvailable,
          projection_reason: projectionReason,
        },
        previous_month: { month: '2026-07', total_kwh: 248.0, total_cost: 286.0, days_in_month: 31 },
        comparison_pct: null,
      } });
    }
    if (pathname === '/api/v1/consumption/period') {
      return route.fulfill({ json: {
        timeframe: 'today', site_name: 'Site', timezone: 'UTC',
        period_start: '2026-07-23T00:00:00Z', period_end: '2026-07-23T12:00:00Z', granularity: 'hour',
        sample_count: 12, total_kwh: 10, estimated_cost: 11, currency: 'MAD', average_kw: 1.0, peak_kw: 2.0, peak_at: null,
        coverage_pct: 95.0, sources: [], freshness: { status: 'fresh', last_seen_at: null, age_seconds: 0 }, points: [],
      } });
    }
    return route.fulfill({ status: 200, json: {} });
  });

  // State 1: Projection available on Dashboard -> displays "Projected MAD 302.70 at 95.0% coverage"
  await page.goto('/dashboard');
  await expect(page.getByText('MAD 84.20 / 280.00')).toBeVisible();
  await expect(page.getByText('Projected MAD 302.70 at 95.0% coverage')).toBeVisible();
  await expect(page.getByText('Likely to exceed budget by MAD 22.70')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Compared with July 2026' })).toBeVisible();
  await expect(page.getByText('248.00 kWh')).toBeVisible();
  await expect(page.getByText('Your daily average is 12.5% above last month.')).toBeVisible();
  await expect(page.getByText('Shift flexible loads away from the evening peak')).toBeVisible();

  // State 2: Projection unavailable (early_period) -> displays spent_mad without the word "Projected"
  projectionAvailable = false;
  projectionReason = 'early_period';
  await page.reload();
  await expect(page.getByText('MAD 84.20 / 280.00')).toBeVisible();
  await expect(page.getByText('Estimate available after the first 24 hours of the month.')).toBeVisible();
  await expect(page.locator('section[aria-label="Operational summary"]').getByText(/Projected/)).toHaveCount(0);

  // State 3: Projection unavailable (insufficient_coverage)
  projectionReason = 'insufficient_coverage';
  await page.reload();
  await expect(page.getByText('Projection paused because data coverage is below 50%.')).toBeVisible();
  await expect(page.locator('section[aria-label="Operational summary"]').getByText(/Projected/)).toHaveCount(0);

  // State 4: Projection unavailable (no_readings)
  projectionReason = 'no_readings';
  await page.reload();
  await expect(page.getByText('No meter readings recorded yet this month.')).toBeVisible();
  await expect(page.locator('section[aria-label="Operational summary"]').getByText(/Projected/)).toHaveCount(0);
});
