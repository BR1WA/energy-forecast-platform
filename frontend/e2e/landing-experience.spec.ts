import { expect, test, type Page } from '@playwright/test';

// All API traffic is intercepted. These journeys never touch Azure or send email.
async function session(page: Page, options: { registration?: boolean; unavailable?: boolean; authenticated?: boolean } = {}) {
  await page.route('http://localhost:8000/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/capabilities')) return route.fulfill({ status: options.unavailable ? 503 : 200, json: { email_delivery_enabled: options.registration ?? false, google_auth_enabled: false } });
    if (path.endsWith('/auth/refresh')) return route.fulfill({ status: options.authenticated ? 200 : 401, json: options.authenticated ? { access_token: 'controlled-preview-token' } : {} });
    if (path.endsWith('/auth/me') && options.authenticated) return route.fulfill({ json: { id: 71, email: 'preview@example.com', full_name: 'Preview User', role: 'user', is_active: true, is_setup_complete: true } });
    if (path.endsWith('/settings/setup-status')) return route.fulfill({ json: { is_setup_complete: true } });
    return route.fulfill({ status: 404, json: {} });
  });
}

for (const state of ['enabled', 'disabled', 'unavailable'] as const) {
  test(`landing preserves capability-gated access: ${state}`, async ({ page }) => {
    await session(page, { registration: state === 'enabled', unavailable: state === 'unavailable' });
    await page.goto('/');
    const cta = page.locator('header').getByRole('link', { name: state === 'enabled' ? 'Create account' : 'Sign in', exact: true });
    await expect(cta).toHaveAttribute('href', state === 'enabled' ? '/register' : '/login');
    if (state === 'enabled') await expect(page.locator('header').getByRole('link', { name: 'Sign in', exact: true })).toHaveAttribute('href', '/login');
    if (state !== 'enabled') {
      await expect(page.getByText('Public registration is currently unavailable.', { exact: false })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Create account', exact: true })).toHaveCount(0);
    }
    await cta.click();
    await expect(page).toHaveURL(new RegExp(state === 'enabled' ? '/register$' : '/login$'));
  });
}

test('returning users are offered their dashboard', async ({ page }) => {
  await session(page, { authenticated: true });
  await page.goto('/');
  await expect(page.locator('header').getByRole('link', { name: 'Open dashboard' })).toHaveAttribute('href', '/dashboard');
  await expect(page.getByText('Public registration is currently unavailable.', { exact: false })).toHaveCount(0);
});

test('forecast explorer preserves model contracts and labels illustration', async ({ page }) => {
  await session(page);
  await page.goto('/');
  const section = page.locator('#forecasts');
  await section.scrollIntoViewIfNeeded();
  await expect(section.getByText('Illustrative pattern, not a prediction or measured consumption.')).toBeVisible();
  await expect(section.getByRole('button', { name: '24 hours' })).toHaveAttribute('aria-pressed', 'true');
  await section.getByRole('button', { name: '7 days' }).click();
  await expect(section.locator('[aria-live="polite"]')).toContainText('168hourly targets');
  await section.getByRole('button', { name: '30 days' }).click();
  await expect(section.locator('[aria-live="polite"]')).toContainText('30daily targets');
  await expect(section.locator('[aria-live="polite"]')).toContainText('Chronos-2 LoRA');
  await expect(section.getByText('At least 270 daily blocks')).toBeVisible();
  await expect(section.getByText('30 daily targets — not a 720-step hourly forecast.')).toBeVisible();
  await section.getByRole('button', { name: '24 hours' }).click();
  await expect(section.getByText('336 hours of history')).toBeVisible();
  await expect(section.getByText('30 daily targets — not a 720-step hourly forecast.')).toHaveCount(0);
});

test('scroll rotates the model and pause freezes decorative motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await session(page);
  await page.goto('/');
  const scene = page.getByTestId('energy-scene');
  await scene.scrollIntoViewIfNeeded();
  await expect(scene).toHaveAttribute('data-offscreen', 'false');
  const rotation = () => scene.evaluate((element) => element.style.getPropertyValue('--scene-turn'));
  await expect.poll(rotation).not.toBe('');
  const initial = await rotation();
  await page.evaluate(() => window.scrollBy(0, 80));
  await expect.poll(rotation).not.toBe(initial);
  await page.getByRole('button', { name: 'Pause decorative motion' }).click();
  await expect(page.getByRole('button', { name: 'Resume decorative motion' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(rotation).toBe('-34deg');
  await page.evaluate(() => window.scrollBy(0, 20));
  await expect.poll(rotation).toBe('-34deg');
  expect(await scene.locator('path').nth(1).evaluate((element) => getComputedStyle(element).animationPlayState)).toBe('paused');
  await page.getByRole('button', { name: 'Resume decorative motion' }).click();
  await expect(page.getByRole('button', { name: 'Pause decorative motion' })).toHaveAttribute('aria-pressed', 'false');
});

test('reduced motion disables animation and keeps all content accessible', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await session(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  const scene = page.getByTestId('energy-scene');
  await scene.scrollIntoViewIfNeeded();
  expect(await scene.locator('path').nth(1).evaluate((element) => getComputedStyle(element).animationName)).toBe('none');
  await expect.poll(() => scene.evaluate((element) => element.style.getPropertyValue('--scene-turn'))).toBe('-34deg');
  await page.evaluate(() => window.scrollBy(0, 80));
  await expect.poll(() => scene.evaluate((element) => element.style.getPropertyValue('--scene-turn'))).toBe('-34deg');
  for (const section of ['#workflow', '#forecasts']) {
    await page.locator(section).scrollIntoViewIfNeeded();
    await expect(page.locator(section).getByRole('heading', { level: 2 })).toBeVisible();
  }
});

test('scene retains an isometric illustration when the renderer flattens depth', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await session(page);
  await page.goto('/');
  const scene = page.getByTestId('energy-scene');
  await expect(scene).toHaveAttribute('data-flat', /true|false/);
  const flattened = await scene.locator('[data-depth-probe]').evaluate((element) => {
    const roof = element as HTMLElement;
    const elevated = roof.getBoundingClientRect().top;
    roof.style.transform = 'translateZ(0)';
    const flat = roof.getBoundingClientRect().top;
    roof.style.removeProperty('transform');
    return Math.abs(elevated - flat) < 1;
  });
  await expect(scene).toHaveAttribute('data-flat', String(flattened));
  if (flattened) {
    await expect(page.getByTestId('projected-site')).toBeVisible();
    expect(await page.getByTestId('projected-site').locator('polygon').count()).toBeGreaterThan(50);
  } else {
    await expect(page.getByTestId('projected-site')).toBeHidden();
    await expect(scene.locator('[data-depth-probe]')).toBeVisible();
  }
});

test('landing fits the viewport in both saved themes without runtime errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await session(page);
  await page.goto('/');
  for (const theme of ['dark', 'light']) {
    await page.evaluate((value) => localStorage.setItem('theme', value), theme);
    await page.reload();
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.locator('html')).toHaveClass(new RegExp(theme));
    await page.locator('#forecasts').scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    for (const selector of ['header', '#overview h1', '#forecasts']) {
      const bounds = await page.locator(selector).boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.x).toBeGreaterThanOrEqual(-1);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
    }
  }
  expect(errors).toEqual([]);
});
