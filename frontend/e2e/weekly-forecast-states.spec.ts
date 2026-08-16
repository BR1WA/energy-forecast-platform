import { expect, test } from '@playwright/test';

const API = 'http://localhost:8000';
const USER = {
  id: 93,
  email: 'weekly-states@example.com',
  full_name: 'Weekly States',
  role: 'user',
  is_active: true,
  is_setup_complete: true,
  email_verified_at: '2026-07-27T08:00:00Z',
};

function model(horizon: 24 | 168 | 720) {
  return { available: true, enabled: true, warmed: true, horizon_hours: horizon, name: `global_tft_${horizon}h`, display_name: `${horizon} hour TFT`, version: '1.0', artifact_fingerprint: `fingerprint-${horizon}`, error: null };
}

function capabilities(includeWeek = true) {
  return {
    default_horizon_hours: 24,
    capabilities: [
      { horizon_hours: 24, target_count: 24, target_interval_hours: 1, resolution: 'hourly', label: 'Next 24 hours', description: '24 hours', model: model(24) },
      ...(includeWeek ? [{ horizon_hours: 168, target_count: 168, target_interval_hours: 1, resolution: 'hourly', label: 'Next 7 days', description: '168 hours', model: model(168) }] : []),
    ],
  };
}

function readiness(status: 'ready' | 'insufficient_data') {
  return {
    horizon_hours: 168,
    target_count: 168,
    target_interval_hours: 1,
    status,
    ready_for_model: status === 'ready',
    ready_for_tft: status === 'ready',
    fallback_available: status === 'ready',
    required_hours: 336,
    minimum_coverage_percent: 95,
    maximum_allowed_gap_hours: 3,
    coverage_percent: status === 'ready' ? 100 : 42,
    observed_hours: status === 'ready' ? 336 : 140,
    missing_hours: status === 'ready' ? 0 : 196,
    imputed_hours: 0,
    maximum_gap_hours: status === 'ready' ? 0 : 12,
    required_days: null,
    observed_days: 0,
    missing_days: 0,
    imputed_days: 0,
    maximum_gap_days: 0,
    unit: 'kWh',
    resolution: 'hourly',
    latest_reading_at: '2026-07-23T00:00:00Z',
    forecast_origin: '2026-07-23T00:00:00Z',
    reasons: status === 'ready' ? [] : ['History coverage is 42.0%; at least 95% of 336 hours is required.'],
    model: model(168),
  };
}

test('weekly loading resolves to an actionable readiness-blocked state', async ({ page }) => {
  let releaseReadiness!: () => void;
  const readinessGate = new Promise<void>((resolve) => { releaseReadiness = resolve; });
  let demoPrepared = false;
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'weekly-blocked-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/forecast/capabilities') return route.fulfill({ json: capabilities() });
    if (pathname === '/api/v1/forecast/prepare-demo-history') {
      demoPrepared = true;
      return route.fulfill({ json: { status: 'ready', meter_id: 1, synthetic_source: 'forecast_demo', required_hours: 336, accepted_rows: 337, duplicate_rows: 0, coverage_percent: 100, observed_hours: 336, maximum_gap_hours: 0, forecast_origin: '2026-07-23T00:00:00Z', message: 'Forecast demo history is ready. Existing meter readings were preserved.' } });
    }
    if (pathname === '/api/v1/forecast/readiness') {
      await readinessGate;
      return route.fulfill({ json: readiness(demoPrepared ? 'ready' : 'insufficient_data') });
    }
    if (pathname === '/api/v1/forecast/latest') return route.fulfill({ json: null });
    if (pathname === '/api/v1/forecast/history') return route.fulfill({ json: [] });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/forecast?horizon=168');
  await expect(page.getByRole('heading', { name: 'Next 7 days · 168-hour energy forecast' })).toBeVisible();
  await expect(page.getByText('Loading')).toHaveCount(3);
  releaseReadiness();
  await expect(page.getByText('More meter history is required')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open Usage' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Download forecast-ready CSV' })).toBeVisible();
  await page.getByRole('button', { name: 'Prepare demo history' }).click();
  await expect(page.getByText('More meter history is required')).toHaveCount(0);
  await expect(page.getByText('No persisted 7-day / 168-hour forecast yet.')).toBeVisible();
});

test('weekly empty and error states remain horizon-specific', async ({ page }) => {
  let failReadiness = false;
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'weekly-empty-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/forecast/capabilities') return route.fulfill({ json: capabilities() });
    if (pathname === '/api/v1/forecast/readiness' && failReadiness) {
      return route.fulfill({ status: 503, json: { detail: { code: 'FORECAST_ARTIFACT_NOT_READY', message: 'The 7-day / 168-hour model artifact could not be loaded.' } } });
    }
    if (pathname === '/api/v1/forecast/readiness') return route.fulfill({ json: readiness('ready') });
    if (pathname === '/api/v1/forecast/latest') return route.fulfill({ json: null });
    if (pathname === '/api/v1/forecast/history') return route.fulfill({ json: [] });
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/forecast?horizon=168');
  await expect(page.getByText('No persisted 7-day / 168-hour forecast yet.')).toBeVisible();
  failReadiness = true;
  await page.reload();
  await expect(page.getByText('The 7-day / 168-hour model artifact could not be loaded.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Next 7 days · 168-hour energy forecast' })).toBeVisible();
});

test('disabled weekly capability is not advertised or silently replaced with 24 hours', async ({ page }) => {
  let weeklyDataRequests = 0;
  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'weekly-disabled-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/forecast/capabilities') return route.fulfill({ json: capabilities(false) });
    if (pathname.startsWith('/api/v1/forecast/') && url.searchParams.get('horizon_hours') === '168') weeklyDataRequests += 1;
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/forecast?horizon=168');
  await expect(page.getByText('The 7-day / 168-hour forecast is unavailable in this runtime. Ask the operator to enable and warm its packaged model.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Next 7 days' })).toHaveCount(0);
  expect(weeklyDataRequests).toBe(0);
  await expect(page).toHaveURL(/\/forecast\?horizon=168$/);
});

test('monthly capability stays daily and offers the contract-safe one-year simulator', async ({ page }) => {
  let resetRequests = 0;
  await page.route(`${API}/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/auth/refresh') return route.fulfill({ json: { access_token: 'monthly-token', token_type: 'bearer' } });
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: USER });
    if (pathname === '/api/v1/settings/setup-status') return route.fulfill({ json: { is_setup_complete: true } });
    if (pathname === '/api/v1/alerts') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/forecast/capabilities') {
      return route.fulfill({ json: {
        default_horizon_hours: 24,
        capabilities: [
          { horizon_hours: 24, target_count: 24, target_interval_hours: 1, resolution: 'hourly', label: 'Next 24 hours', description: '24 hours', model: model(24) },
          { horizon_hours: 720, target_count: 30, target_interval_hours: 24, resolution: 'daily', label: 'Next 30 days', description: '30 daily values', model: { ...model(720), name: 'month_production_v3', display_name: 'Chronos-2 LoRA 30-day daily', version: '3.0.0' } },
        ],
      } });
    }
    if (pathname === '/api/v1/forecast/readiness') return route.fulfill({ json: {
      horizon_hours: 720,
      target_count: 30,
      target_interval_hours: 24,
      status: 'insufficient_data',
      ready_for_model: false,
      ready_for_tft: false,
      fallback_available: false,
      required_hours: 6480,
      required_days: 270,
      minimum_coverage_percent: 95,
      maximum_allowed_gap_hours: 72,
      coverage_percent: 46,
      observed_hours: 4032,
      missing_hours: 2448,
      imputed_hours: 0,
      maximum_gap_hours: 240,
      observed_days: 168,
      missing_days: 102,
      imputed_days: 0,
      maximum_gap_days: 10,
      unit: 'kWh',
      resolution: 'daily',
      latest_reading_at: '2026-07-23T00:00:00Z',
      forecast_origin: '2026-07-23T00:00:00Z',
      reasons: ['Only 168 complete daily blocks are available; at least 270 are required.'],
      model: { ...model(720), name: 'month_production_v3', display_name: 'Chronos-2 LoRA 30-day daily', version: '3.0.0' },
    } });
    if (pathname === '/api/v1/forecast/latest') return route.fulfill({ json: null });
    if (pathname === '/api/v1/forecast/history') return route.fulfill({ json: [] });
    if (pathname === '/api/v1/simulation/reset') {
      resetRequests += 1;
      return route.fulfill({ json: { status: 'reset' } });
    }
    return route.fulfill({ status: 200, json: {} });
  });

  await page.goto('/forecast?horizon=720');
  await expect(page.getByRole('heading', { name: 'Next 30 days · daily energy forecast' })).toBeVisible();
  await expect(page.getByText('168 / 270')).toBeVisible();
  await expect(page.getByText("The production monthly model requires at least 270 complete rolling daily blocks. The simulator creates 365 days at the models' native hourly resolution, without padding history or lowering this gate. This replaces only existing demo-simulator readings; imported or measured readings are preserved.")).toBeVisible();
  await expect(page.getByRole('button', { name: 'Prepare demo history' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Create one-year demo history' }).click();
  await expect.poll(() => resetRequests).toBe(1);
  await expect(page).toHaveURL(/\/forecast\?horizon=720$/);
  await expect(page.getByRole('link', { name: 'Download forecast-ready CSV' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Next 30 days' })).toBeVisible();
});
