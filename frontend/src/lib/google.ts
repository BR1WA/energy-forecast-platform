'use client';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(options: { client_id: string; nonce: string; callback: (response: { credential: string }) => void }): void;
          prompt(callback?: (notification: { isNotDisplayed(): boolean; getNotDisplayedReason(): string }) => void): void;
          renderButton?(parent: HTMLElement, options: { theme: string; size: string; width: number }): void;
        };
      };
    };
  }
}

let scriptPromise: Promise<void> | null = null;

function loadGoogleIdentityScript(): Promise<void> {
  if (window.google) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-energy-google-identity]');
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('Google sign-in could not be loaded.')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.dataset.energyGoogleIdentity = 'true';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Google sign-in could not be loaded.'));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export async function requestGoogleCredential(clientId: string, nonce: string): Promise<string> {
  await loadGoogleIdentityScript();
  if (!window.google) throw new Error('Google sign-in is unavailable.');
  return new Promise((resolve, reject) => {
    let settled = false;
    let closeLocalDialog = () => {};
    window.google!.accounts.id.initialize({
      client_id: clientId,
      nonce,
      callback: (response) => {
        if (settled) return;
        settled = true;
        closeLocalDialog();
        resolve(response.credential);
      },
    });
    // One Tap requires HTTPS. Google's user-clicked popup button supports local HTTP.
    if (window.location.protocol === 'http:' && window.location.hostname === 'localhost') {
      const renderButton = window.google!.accounts.id.renderButton;
      if (!renderButton) {
        reject(new Error('Google sign-in could not be loaded. Please reload and try again.'));
        return;
      }
      const dialog = document.createElement('dialog');
      dialog.setAttribute('aria-label', 'Sign in with Google');
      dialog.style.cssText = 'margin:auto;padding:24px;border:1px solid #334155;border-radius:16px;background:#0d1420;color:#e2e8f0;max-width:calc(100vw - 32px)';
      const title = document.createElement('h2');
      title.textContent = 'Choose your Google account';
      title.style.cssText = 'margin:0 0 16px;font-size:18px;font-weight:600';
      const buttonHost = document.createElement('div');
      const cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.textContent = 'Cancel';
      cancel.style.cssText = 'display:block;margin:16px auto 0;padding:8px 16px;cursor:pointer';
      closeLocalDialog = () => { dialog.close(); dialog.remove(); };
      const cancelSignIn = () => {
        if (settled) return;
        settled = true;
        closeLocalDialog();
        reject(new Error('Google sign-in was cancelled.'));
      };
      cancel.addEventListener('click', cancelSignIn);
      dialog.addEventListener('cancel', (event) => { event.preventDefault(); cancelSignIn(); });
      dialog.append(title, buttonHost, cancel);
      document.body.append(dialog);
      dialog.showModal();
      try {
        renderButton.call(window.google!.accounts.id, buttonHost, { theme: 'outline', size: 'large', width: 280 });
      } catch {
        settled = true;
        closeLocalDialog();
        reject(new Error('Google sign-in could not be loaded. Please reload and try again.'));
      }
      return;
    }
    window.google!.accounts.id.prompt((notification) => {
      if (!settled && notification.isNotDisplayed()) {
        reject(new Error(`Google sign-in is unavailable (${notification.getNotDisplayedReason()}).`));
      }
    });
  });
}
