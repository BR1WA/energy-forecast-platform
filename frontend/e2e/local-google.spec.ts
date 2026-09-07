import { expect, test } from '@playwright/test';

test('local HTTP Google popup preserves the challenge and can be cancelled and retried', async ({ page }) => {
  const submissions: unknown[] = [];
  await page.addInitScript(() => {
    let callback: (value: { credential: string }) => void;
    window.google = { accounts: { id: {
      initialize(options) {
        if (options.nonce !== 'controlled-local-google-nonce') throw new Error('Missing nonce');
        callback = options.callback;
      },
      prompt() { throw new Error('HTTP localhost must not invoke One Tap'); },
      renderButton(parent) {
        const button = document.createElement('button');
        button.textContent = 'Controlled Google account';
        button.onclick = () => callback({ credential: 'controlled-local-google-credential' });
        parent.append(button);
      },
    } } };
  });
  await page.route('http://localhost:8000/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/refresh')) return route.fulfill({ status: 401, json: {} });
    if (path.endsWith('/auth/capabilities')) return route.fulfill({ json: { email_delivery_enabled: true, google_auth_enabled: true, google_client_id: 'browser-client.apps.example.test' } });
    if (path.endsWith('/auth/google/challenge')) return route.fulfill({ json: { nonce: 'controlled-local-google-nonce', state: 'controlled-local-google-state', expires_in_seconds: 300 } });
    if (path.endsWith('/auth/google')) {
      submissions.push(route.request().postDataJSON());
      return route.fulfill({ status: 401, json: { detail: { code: 'test_rejected', message: 'Controlled test rejection' } } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('http://localhost:3100/login');
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  const dialog = page.getByRole('dialog', { name: 'Sign in with Google' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText('Google sign-in was cancelled.')).toBeVisible();
  expect(submissions).toEqual([]);
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await dialog.getByRole('button', { name: 'Controlled Google account' }).click();
  await expect(dialog).toHaveCount(0);
  await expect.poll(() => submissions).toEqual([{ credential: 'controlled-local-google-credential', state: 'controlled-local-google-state' }]);
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeEnabled();
  expect(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }))).toEqual({ local: [], session: [] });
});
